from __future__ import annotations

import hashlib
import json
import logging

from django.conf import settings
from django.core.cache import cache
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import parsers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from duo_project.cloudinary_media.cleanup import delete_cloudinary_url
from duo_project.cloudinary_upload import (
    CloudinaryNotConfiguredError,
    _validate_profile_image,
    upload_profile_photo_result,
)
from photo_verification.constants import ModerationStatus, RejectionCategory
from photo_verification.models import PhotoAnalysis, ProfilePhoto
from photo_verification.serializers import (
    PhotoAnalysisSerializer,
    PhotoReorderSerializer,
    PhotoUploadResponseSerializer,
    ProfilePhotoSerializer,
)
from photo_verification.services.pipeline import PhotoVerificationPipeline
from photo_verification.services.profile_photo_sync import sync_profile_photos
from photo_verification.throttling import PhotoUploadBurstThrottle, PhotoUploadDailyThrottle

logger = logging.getLogger("duo.photos")

IDEMPOTENCY_HEADER = "HTTP_IDEMPOTENCY_KEY"
MAX_IDEMPOTENCY_KEY_LENGTH = 128


def _error(code: str, message: str, http_status: int, **extra) -> Response:
    """Error body shared with duo_project.exceptions: code + message + detail."""
    return Response({"code": code, "message": message, "detail": message, **extra}, status=http_status)


def _save_analysis(user, image_url: str, result, *, is_primary: bool) -> PhotoAnalysis:
    return PhotoAnalysis.objects.create(
        user=user,
        image_url=image_url,
        image_hash=result.image_hash,
        embedding=result.embedding,
        face_detected=result.face_detected,
        face_count=result.face_count,
        face_centered=result.face_centered,
        blur_score=result.blur_score,
        brightness_score=result.brightness_score,
        resolution_passed=result.resolution_passed,
        image_width=result.image_width,
        image_height=result.image_height,
        quality_score=result.quality_score,
        ai_generated_probability=result.ai_generated_probability,
        duplicate_probability=result.duplicate_probability,
        status=result.status.value,
        warnings=result.warnings,
        rejection_reasons=result.rejection_reasons,
        is_primary=is_primary,
    )


class PhotoUploadView(APIView):
    """
    Upload a profile image, run AI verification + content-safety moderation,
    and persist to Cloudinary + a ProfilePhoto record.

    A photo only ever becomes visible to other users once it is set on
    accounts.Profile.photo_url/photo_urls, which is only permitted for
    APPROVED ProfilePhoto rows (enforced in accounts.ProfileSerializer).
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]
    throttle_classes = [PhotoUploadBurstThrottle, PhotoUploadDailyThrottle]

    # -- Throttling is deferred --------------------------------------------
    # DRF normally throttles in initial(), before the handler runs. That makes
    # a wrong file type or an oversized file cost upload quota. We skip the
    # automatic check and enforce it in post() after cheap validation, so only
    # uploads that reach AI verification + storage count.
    def check_throttles(self, request):
        return None

    def _enforce_throttles(self, request):
        APIView.check_throttles(self, request)

    # -- Idempotency -------------------------------------------------------
    # The client sends one Idempotency-Key per photo and reuses it on retry.
    # A retry after a lost response replays the stored result instead of
    # re-running verification, creating a duplicate ProfilePhoto, or using quota.
    def _idempotency_cache_key(self, request) -> str | None:
        raw = (request.META.get(IDEMPOTENCY_HEADER) or "").strip()
        if not raw or len(raw) > MAX_IDEMPOTENCY_KEY_LENGTH:
            return None
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"photo_upload:idem:{request.user.id}:{digest}"

    @staticmethod
    def _cache_get(key):
        try:
            return cache.get(key)
        except Exception:
            logger.warning("photo_upload_idempotency_cache_read_failed", exc_info=True)
            return None

    @staticmethod
    def _remember(key: str | None, response: Response) -> Response:
        if not key:
            return response
        try:
            data = json.loads(json.dumps(response.data, cls=DjangoJSONEncoder))
            cache.set(
                key,
                {"status": response.status_code, "data": data},
                timeout=getattr(settings, "PHOTO_UPLOAD_IDEMPOTENCY_TTL", 86400),
            )
        except Exception:
            logger.warning("photo_upload_idempotency_cache_write_failed", exc_info=True)
        return response

    @extend_schema(
        tags=["Photos"],
        summary="Upload and analyze profile photo",
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "image": {"type": "string", "format": "binary"},
                    "is_primary": {"type": "boolean", "default": False},
                },
                "required": ["image"],
            }
        },
        responses={200: PhotoUploadResponseSerializer, 201: PhotoUploadResponseSerializer},
    )
    def post(self, request):
        # 1. Replay a completed request with the same idempotency key.
        idem_key = self._idempotency_cache_key(request)
        if idem_key:
            cached = self._cache_get(idem_key)
            if cached:
                replay = Response(cached["data"], status=cached["status"])
                replay["Idempotent-Replayed"] = "true"
                return replay

        # 2. Cheap validation first. These failures never cost quota.
        image = request.FILES.get("image")
        if not image:
            return _error("no_image", "Please choose a photo to upload.", status.HTTP_400_BAD_REQUEST)
        try:
            _validate_profile_image(image)
            image.seek(0)
        except ValueError as exc:
            message = str(exc)
            code = "file_too_large" if "too large" in message.lower() else "invalid_file"
            return _error(code, message, status.HTTP_400_BAD_REQUEST)

        # 3. Only now count this upload against the rate limits (raises 429).
        self._enforce_throttles(request)

        is_primary = str(request.data.get("is_primary", "false")).lower() in ("1", "true", "yes")

        pipeline = PhotoVerificationPipeline()
        try:
            result = pipeline.analyze_file(image, user_id=request.user.id, is_primary=is_primary)
        except Exception as exc:
            logger.exception("photo_analysis_failed user_id=%s", request.user.id)
            message = "We couldn't analyze this photo. Please try again or use a different photo."
            if settings.DEBUG:
                message = f"Image analysis failed: {exc}"
            return _error("analysis_failed", message, status.HTTP_502_BAD_GATEWAY)

        # Note: no special-cased "no face detected" branch here. score_and_decide
        # already forces PhotoStatus.REJECTED with "No human face detected." in
        # quality.rejection_reasons whenever a face isn't found, and
        # decide_final_photo_status folds that into moderation_status via the
        # unified path below — but content-safety issues (gore/weapon/hate/etc)
        # are checked independently of face detection and correctly take
        # priority there. A special early branch here would have hidden a real
        # safety flag behind a misleading "no face" message whenever both were
        # true (e.g. a faceless gore/weapon photo).
        strict_reject = getattr(settings, "PHOTO_VERIFICATION_STRICT_REJECT", True)
        is_quality_only_reject = (
            result.moderation_status == ModerationStatus.REJECTED
            and result.moderation_rejection_category == RejectionCategory.QUALITY
        )
        # Content-safety rejections (nudity/violence/hate/etc) are always
        # strict, regardless of the quality-pipeline's leniency setting —
        # that toggle was only ever meant for blur/resolution/duplicate
        # rejections, never for unsafe content.
        should_block_upload = result.moderation_status == ModerationStatus.REJECTED and (
            not is_quality_only_reject or strict_reject
        )

        if should_block_upload:
            record = _save_analysis(request.user, "", result, is_primary=is_primary)
            ProfilePhoto.objects.create(
                user=request.user,
                url="",
                status=ModerationStatus.REJECTED,
                rejection_reason=result.moderation_rejection_reason or "This photo couldn't be approved.",
                rejection_category=result.moderation_rejection_category.value,
                moderation_source=result.moderation_source,
                moderated_at=timezone.now(),
                order=ProfilePhoto.objects.filter(user=request.user).count(),
                photo_analysis=record,
            )
            message = result.moderation_rejection_reason or "This photo couldn't be approved."
            return self._remember(
                idem_key,
                Response(
                    {
                        "success": False,
                        "code": "photo_rejected",
                        "message": message,
                        "image_url": "",
                        "analysis": PhotoAnalysisSerializer(record).data,
                        "detail": message,
                    },
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                ),
            )

        # APPROVED or MANUAL_REVIEW both get uploaded/stored — a manual
        # reviewer needs something to actually look at.
        image_url = ""
        try:
            image.seek(0)
            upload_result = upload_profile_photo_result(image, user_id=request.user.id)
            image_url = upload_result.image_url
        except CloudinaryNotConfiguredError as exc:
            logger.error("photo_storage_not_configured: %s", exc)
            message = str(exc) if settings.DEBUG else "Photo storage is temporarily unavailable. Please try again later."
            return _error("storage_unavailable", message, status.HTTP_503_SERVICE_UNAVAILABLE)
        except ValueError as exc:
            return _error("invalid_file", str(exc), status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("photo_storage_upload_failed user_id=%s", request.user.id)
            return _error(
                "upload_failed",
                "We couldn't save your photo. Please try again.",
                status.HTTP_502_BAD_GATEWAY,
            )

        record = _save_analysis(request.user, image_url, result, is_primary=is_primary)

        photo = ProfilePhoto.objects.create(
            user=request.user,
            url=image_url,
            status=result.moderation_status,
            rejection_reason=result.moderation_rejection_reason,
            rejection_category=result.moderation_rejection_category.value,
            moderation_source=result.moderation_source,
            moderated_at=timezone.now(),
            order=ProfilePhoto.objects.filter(user=request.user).count(),
            is_primary=False,  # set via sync/explicit set-primary, never implicitly here
            photo_analysis=record,
        )

        if result.moderation_status == ModerationStatus.APPROVED:
            from notifications.dispatch import dispatch_photo_approved_push

            dispatch_photo_approved_push(user_id=request.user.id)
            sync_profile_photos(request.user)

        if image_url:
            try:
                from duo_project.tasks.enqueue import safe_delay
                from duo_project.tasks.verification import create_photo_embedding_task

                safe_delay(
                    create_photo_embedding_task,
                    request.user.id,
                    image_url,
                    record.id if record else None,
                    result.quality_score,
                    is_primary,
                )
            except Exception:
                pass

        http_status = status.HTTP_201_CREATED if image_url else status.HTTP_200_OK
        payload = {
            "success": True,
            "image_url": image_url,
            "analysis": PhotoAnalysisSerializer(record).data,
            "photo": ProfilePhotoSerializer(photo).data,
        }
        if upload_result.media:
            payload["media"] = upload_result.media
        return self._remember(idem_key, Response(payload, status=http_status))


class MyProfilePhotosView(APIView):
    """List the authenticated user's own ProfilePhoto rows — including
    pending/rejected/manual-review ones, which are never exposed to anyone
    else. Powers the profile-edit UI's per-card states."""

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Photos"], summary="List my profile photos", responses={200: ProfilePhotoSerializer(many=True)})
    def get(self, request):
        photos = ProfilePhoto.objects.filter(user=request.user).order_by("order", "uploaded_at")
        return Response(ProfilePhotoSerializer(photos, many=True).data)


class PhotoReorderView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Photos"], summary="Reorder my profile photos", request=PhotoReorderSerializer)
    def patch(self, request):
        serializer = PhotoReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        photo_ids = serializer.validated_data["photo_ids"]

        owned = {
            p.id: p
            for p in ProfilePhoto.objects.filter(user=request.user, id__in=photo_ids)
        }
        if len(owned) != len(set(photo_ids)):
            return Response({"detail": "One or more photos were not found."}, status=status.HTTP_404_NOT_FOUND)

        for index, photo_id in enumerate(photo_ids):
            photo = owned[photo_id]
            if photo.order != index:
                photo.order = index
                photo.save(update_fields=["order"])

        photos = ProfilePhoto.objects.filter(user=request.user).order_by("order", "uploaded_at")
        return Response(ProfilePhotoSerializer(photos, many=True).data)


class PhotoSetPrimaryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Photos"], summary="Set a photo as my primary profile photo")
    def post(self, request, pk: int):
        try:
            photo = ProfilePhoto.objects.get(pk=pk, user=request.user)
        except ProfilePhoto.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if photo.status != ModerationStatus.APPROVED:
            return Response(
                {"detail": "Only an approved photo can be set as primary."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ProfilePhoto.objects.filter(user=request.user, is_primary=True).update(is_primary=False)
        photo.is_primary = True
        photo.save(update_fields=["is_primary"])
        sync_profile_photos(request.user)

        photos = ProfilePhoto.objects.filter(user=request.user).order_by("order", "uploaded_at")
        return Response(ProfilePhotoSerializer(photos, many=True).data)


class PhotoDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Photos"], summary="Delete one of my profile photos")
    def delete(self, request, pk: int):
        try:
            photo = ProfilePhoto.objects.get(pk=pk, user=request.user)
        except ProfilePhoto.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        url = photo.url
        photo.delete()

        if url:
            try:
                delete_cloudinary_url(url)
            except Exception:
                pass  # best-effort cleanup; never fail the request over it

        sync_profile_photos(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PhotoAnalysisDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Photos"],
        summary="Get photo analysis by ID",
        responses={200: PhotoAnalysisSerializer},
    )
    def get(self, request, pk: int):
        try:
            record = PhotoAnalysis.objects.get(pk=pk, user=request.user)
        except PhotoAnalysis.DoesNotExist:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PhotoAnalysisSerializer(record).data)
