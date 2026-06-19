from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    RegisterView,
    MeView,
    GoogleAuthView,
    FirebasePhoneVerifyView,
    FirebaseAuthView,
    EmailOtpSendView,
    EmailOtpVerifyView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('google/', GoogleAuthView.as_view(), name='google_auth'),
    path('email/send-otp/', EmailOtpSendView.as_view(), name='email_send_otp'),
    path('email/verify-otp/', EmailOtpVerifyView.as_view(), name='email_verify_otp'),
    path('firebase/verify-phone/', FirebasePhoneVerifyView.as_view(), name='firebase_verify_phone'),
    path('firebase/', FirebaseAuthView.as_view(), name='firebase_auth'),
    path('refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('me/', MeView.as_view(), name='me'),
]
