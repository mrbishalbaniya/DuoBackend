from django.urls import path

from photo_verification.verification_views import (
    VerificationHistoryView,
    VerificationLivenessView,
    VerificationSelfieView,
    VerificationStartView,
    VerificationStatusView,
    VerificationVerifyView,
)

urlpatterns = [
    path("start/", VerificationStartView.as_view(), name="verification-start"),
    path("liveness/", VerificationLivenessView.as_view(), name="verification-liveness"),
    path("selfie/", VerificationSelfieView.as_view(), name="verification-selfie"),
    path("verify/", VerificationVerifyView.as_view(), name="verification-verify"),
    path("status/", VerificationStatusView.as_view(), name="verification-status"),
    path("history/", VerificationHistoryView.as_view(), name="verification-history"),
]
