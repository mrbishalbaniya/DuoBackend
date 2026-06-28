from __future__ import annotations

from django.conf import settings
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import parsers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from duo_project.cloudinary_upload import CloudinaryNotConfiguredError, upload_verification_selfie
from photo_verification.constants import LIVENESS_STEPS, VerificationStatus
from photo_verification.models import UserVerification
from photo_verification.services.image_utils import load_image_from_file
from photo_verification.services.liveness_detection import capture_baseline_metrics, validate_liveness_step
from photo_verification.services.verification_engine import VerificationEngine
from photo_verification.verification_serializers import (
    LivenessStepResponseSerializer,
    UserVerificationSerializer,
    VerificationStartResponseSerializer,
    VerificationStatusResponseSerializer,
)

INSTRUCTIONS = [
    "Use good lighting and face the camera directly.",
    "Complete each liveness step: smile, blink, turn head left, turn head right.",
    "Take a clear front-facing selfie at the end.",
    "Only one person should be visible.",
]


def _get_session(user, session_token) -> UserVerification | None:
    try:
        return UserVerification.objects.get(
            session_token=session_token,
            user=user,
            expires_at__gt=timezone.now(),
        )
    except UserVerification.DoesNotExist:
        return None


def _status_payload(session: UserVerification) -> dict:
    return {
        "status": session.verification_status,
        "similarity_score": session.similarity_score,
        "liveness_score": session.liveness_score,
        "fraud_probability": session.fraud_probability,
        "verified_badge": session.verification_status == VerificationStatus.VERIFIED.value,
        "rejection_reasons": session.rejection_reasons or [],
        "session": UserVerificationSerializer(session).data,
    }


class VerificationStartView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Verification"],
        summary="Start selfie verification session",
        responses={201: VerificationStartResponseSerializer},
    )
    def post(self, request):
        engine = VerificationEngine()
        existing = engine.get_active_session(request.user)
        session = existing or engine.start_session(request.user)

        return Response(
            {
                "session_id": session.session_token,
                "session_token": session.session_token,
                "expires_at": session.expires_at,
                "instructions": INSTRUCTIONS,
                "liveness_steps": list(LIVENESS_STEPS),
            },
            status=status.HTTP_201_CREATED if not existing else status.HTTP_200_OK,
        )


class VerificationLivenessView(APIView):
    """Submit a liveness challenge frame (smile, blink, head_left, head_right)."""

    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    @extend_schema(
        tags=["Verification"],
        summary="Submit liveness challenge frame",
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "session_token": {"type": "string", "format": "uuid"},
                    "step": {"type": "string", "enum": list(LIVENESS_STEPS)},
                    "image": {"type": "string", "format": "binary"},
                },
                "required": ["session_token", "step", "image"],
            }
        },
        responses={200: LivenessStepResponseSerializer},
    )
    def post(self, request):
        session_token = request.data.get("session_token")
        step = str(request.data.get("step", "")).strip()
        image = request.FILES.get("image")

        if not session_token or not image or step not in LIVENESS_STEPS:
            return Response({"detail": "session_token, step, and image are required."}, status=400)

        session = _get_session(request.user, session_token)
        if not session:
            return Response({"detail": "Invalid or expired session."}, status=404)
        if session.verification_status != VerificationStatus.PENDING.value:
            return Response({"detail": "Session is no longer active."}, status=400)

        loaded = load_image_from_file(image)
        baseline = session.liveness_data.get("_baseline", {}) if session.liveness_data else {}
        if step == "smile" and not baseline:
            baseline = capture_baseline_metrics(loaded.rgb)
            session.liveness_data = {**(session.liveness_data or {}), "_baseline": baseline}

        result = validate_liveness_step(step, loaded.rgb, baseline=baseline)
        liveness_data = dict(session.liveness_data or {})
        liveness_data[step] = {
            "passed": result.passed,
            "score": round(result.score, 4),
            "detail": result.detail,
        }
        session.liveness_data = liveness_data
        session.save(update_fields=["liveness_data", "updated_at"])

        completed = [s for s in LIVENESS_STEPS if liveness_data.get(s, {}).get("passed")]
        return Response(
            {
                "step": result.step,
                "passed": result.passed,
                "score": result.score,
                "detail": result.detail,
                "liveness_steps_completed": completed,
            }
        )


class VerificationSelfieView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    @extend_schema(
        tags=["Verification"],
        summary="Upload verification selfie",
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "session_token": {"type": "string", "format": "uuid"},
                    "image": {"type": "string", "format": "binary"},
                },
                "required": ["session_token", "image"],
            }
        },
        responses={200: VerificationStatusResponseSerializer},
    )
    def post(self, request):
        session_token = request.data.get("session_token")
        image = request.FILES.get("image")
        if not session_token or not image:
            return Response({"detail": "session_token and image are required."}, status=400)

        session = _get_session(request.user, session_token)
        if not session:
            return Response({"detail": "Invalid or expired session."}, status=404)

        engine = VerificationEngine()
        image.seek(0)
        selfie_bytes = image.read()
        image.seek(0)

        try:
            selfie_url = upload_verification_selfie(image, user_id=request.user.id)
        except CloudinaryNotConfiguredError as exc:
            return Response({"detail": str(exc)}, status=503)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)

        result = engine.complete_verification(session, selfie_bytes, selfie_url)
        session.refresh_from_db()

        http_status = (
            status.HTTP_200_OK
            if result.status == VerificationStatus.VERIFIED
            else status.HTTP_422_UNPROCESSABLE_ENTITY
            if result.status == VerificationStatus.REJECTED
            else status.HTTP_202_ACCEPTED
        )
        return Response(_status_payload(session), status=http_status)


class VerificationVerifyView(APIView):
    """Run verification on an already-uploaded selfie URL in session."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Verification"],
        summary="Finalize verification for current session",
        responses={200: VerificationStatusResponseSerializer},
    )
    def post(self, request):
        session_token = request.data.get("session_token")
        if not session_token:
            return Response({"detail": "session_token is required."}, status=400)

        session = _get_session(request.user, session_token)
        if not session:
            return Response({"detail": "Invalid or expired session."}, status=404)
        if not session.selfie_photo_url:
            return Response({"detail": "Upload a selfie first."}, status=400)

        import urllib.request

        with urllib.request.urlopen(session.selfie_photo_url, timeout=20) as resp:
            selfie_bytes = resp.read()

        engine = VerificationEngine()
        result = engine.complete_verification(session, selfie_bytes, session.selfie_photo_url)
        session.refresh_from_db()
        return Response(_status_payload(session))


class VerificationStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Verification"],
        summary="Get current verification status",
        responses={200: VerificationStatusResponseSerializer},
    )
    def get(self, request):
        profile = request.user.profile
        latest = (
            UserVerification.objects.filter(user=request.user)
            .order_by("-created_at")
            .first()
        )
        if not latest:
            return Response(
                {
                    "status": "PENDING",
                    "similarity_score": 0.0,
                    "liveness_score": 0.0,
                    "fraud_probability": 0.0,
                    "verified_badge": profile.is_verified,
                    "rejection_reasons": [],
                }
            )
        payload = _status_payload(latest)
        payload["verified_badge"] = profile.is_verified
        return Response(payload)


class VerificationHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Verification"],
        summary="List verification history",
        responses={200: UserVerificationSerializer(many=True)},
    )
    def get(self, request):
        qs = UserVerification.objects.filter(user=request.user).order_by("-created_at")[:20]
        return Response(UserVerificationSerializer(qs, many=True).data)
