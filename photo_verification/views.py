from __future__ import annotations

from django.conf import settings
from drf_spectacular.utils import extend_schema
from rest_framework import parsers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from duo_project.cloudinary_upload import CloudinaryNotConfiguredError, upload_profile_photo
from photo_verification.constants import PhotoStatus
from photo_verification.models import PhotoAnalysis
from photo_verification.serializers import PhotoAnalysisSerializer, PhotoUploadResponseSerializer
from photo_verification.services.embedding_pipeline import create_embedding_from_upload
from photo_verification.services.pipeline import PhotoVerificationPipeline


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
    Upload a profile image, run AI verification, and optionally persist to Cloudinary.

    Extension points: selfie match, deepfake, ID verification, trust score.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

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
        strict_reject = getattr(settings, "PHOTO_VERIFICATION_STRICT_REJECT", True)

        pipeline = PhotoVerificationPipeline()
        try:
            result = pipeline.analyze_file(image, user_id=request.user.id, is_primary=is_primary)
        except Exception as exc:
            detail = "Image analysis failed. Please try a different photo."
            if settings.DEBUG:
                detail = f"Image analysis failed: {exc}"
            return Response(
                {"detail": detail},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not result.face_detected:
            record = _save_analysis(request.user, "", result, is_primary=is_primary)
            return Response(
                {
                    "success": False,
                    "image_url": "",
                    "analysis": PhotoAnalysisSerializer(record).data,
                    "detail": "No human face detected. Please upload a clear photo showing your face.",
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        if result.status == PhotoStatus.REJECTED and strict_reject:
            record = _save_analysis(request.user, "", result, is_primary=is_primary)
            return Response(
                {
                    "success": False,
                    "image_url": "",
                    "analysis": PhotoAnalysisSerializer(record).data,
                    "detail": "; ".join(result.rejection_reasons) or "Photo rejected.",
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        image_url = ""
        try:
            image.seek(0)
            image_url = upload_profile_photo(image, user_id=request.user.id)
        except CloudinaryNotConfiguredError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        record = _save_analysis(request.user, image_url, result, is_primary=is_primary)

        if image_url:
            try:
                image.seek(0)
                create_embedding_from_upload(
                    request.user,
                    image,
                    photo_url=image_url,
                    photo_analysis=record,
                    quality_score=result.quality_score,
                    is_primary=is_primary,
                )
            except Exception:
                pass

        http_status = status.HTTP_201_CREATED if image_url else status.HTTP_200_OK
        return Response(
            {
                "success": True,
                "image_url": image_url,
                "analysis": PhotoAnalysisSerializer(record).data,
            },
            status=http_status,
        )


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
