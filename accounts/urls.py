from django.urls import path
from .views import (
    RegisterView,
    MeView,
    UsernameUpdateView,
    GoogleAuthView,
    GoogleOAuthCallbackView,
    EmailOtpSendView,
    EmailOtpVerifyView,
    PasswordForgotView,
    PasswordResetView,
    PasswordChangeView,
    DeleteAccountView,
    LoginOtpRequestView,
    LoginOtpVerifyView,
)
from .jwt_views import (
    CookieTokenObtainPairView,
    CookieTokenRefreshView,
    LogoutView,
    AuthHandoffCreateView,
    AuthHandoffExchangeView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', CookieTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('login/otp/request/', LoginOtpRequestView.as_view(), name='login_otp_request'),
    path('login/otp/verify/', LoginOtpVerifyView.as_view(), name='login_otp_verify'),
    path('google/', GoogleAuthView.as_view(), name='google_auth'),
    path('google/callback/', GoogleOAuthCallbackView.as_view(), name='google_oauth_callback'),
    path('email/send-otp/', EmailOtpSendView.as_view(), name='email_send_otp'),
    path('email/verify-otp/', EmailOtpVerifyView.as_view(), name='email_verify_otp'),
    path('password/forgot/', PasswordForgotView.as_view(), name='password_forgot'),
    path('password/reset/', PasswordResetView.as_view(), name='password_reset'),
    path('password/change/', PasswordChangeView.as_view(), name='password_change'),
    path('delete-account/', DeleteAccountView.as_view(), name='delete_account'),
    path('refresh/', CookieTokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('handoff/create/', AuthHandoffCreateView.as_view(), name='auth_handoff_create'),
    path('handoff/exchange/', AuthHandoffExchangeView.as_view(), name='auth_handoff_exchange'),
    path('me/', MeView.as_view(), name='me'),
    path('me/username/', UsernameUpdateView.as_view(), name='me_username'),
]
