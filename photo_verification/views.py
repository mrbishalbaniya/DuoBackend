from __future__ import annotations

from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import parsers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from duo_project.cloudinary_media.cleanup import delete_cloudinary_url
from duo_project.cloudinary_upload import CloudinaryNotConfiguredError, upload_profile_photo_result
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
from photo_verification.throttling import PhotoUploadThrottle


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
    throttle_classes = [PhotoUploadThrottle]

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
        image = request.FILES.get("image") or request.data.get("image")
        if not image:
            return Response({"detail": "No image provided."}, status=status.HTTP_400_BAD_REQUEST)

        is_primary = str(request.data.get("is_primary", "false")).lower() in ("1", "true", "yes")

        pipeline = PhotoVerificationPipeline()
        try:
            result = pipeline.analyze_file(image, user_id=request.user.id, is_primary=is_primary)
        except Exception as exc:
            detail = "Image analysis failed. Please try a different photo."
            if settings.DEBUG:
                detail = f"Image analysis failed: {exc}"
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)

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
            return Response(
                {
                    "success": False,
                    "image_url": "",
                    "analysis": PhotoAnalysisSerializer(record).data,
                    "detail": result.moderation_rejection_reason or "Photo rejected.",
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # APPROVED or MANUAL_REVIEW both get uploaded/stored — a manual
        # reviewer needs something to actually look at.
        image_url = ""
        try:
            image.seek(0)
            upload_result = upload_profile_photo_result(image, user_id=request.user.id)
            image_url = upload_result.image_url
        except CloudinaryNotConfiguredError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

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
        return Response(payload, status=http_status)


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
