from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    RegisterView,
    MeView,
    GoogleAuthView,
    GoogleOAuthCallbackView,
    EmailOtpSendView,
    EmailOtpVerifyView,
    PasswordForgotView,
    PasswordResetView,
    PasswordChangeView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('google/', GoogleAuthView.as_view(), name='google_auth'),
    path('google/callback/', GoogleOAuthCallbackView.as_view(), name='google_oauth_callback'),
    path('email/send-otp/', EmailOtpSendView.as_view(), name='email_send_otp'),
    path('email/verify-otp/', EmailOtpVerifyView.as_view(), name='email_verify_otp'),
    path('password/forgot/', PasswordForgotView.as_view(), name='password_forgot'),
    path('password/reset/', PasswordResetView.as_view(), name='password_reset'),
    path('password/change/', PasswordChangeView.as_view(), name='password_change'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', MeView.as_view(), name='me'),
]
