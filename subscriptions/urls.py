from django.urls import path

from .views import (
    EsewaFailureView,
    EsewaSuccessView,
    InitiatePaymentView,
    SubscriptionPlanView,
    SubscriptionStatusView,
    VerifyPaymentView,
)

urlpatterns = [
    path("plan/", SubscriptionPlanView.as_view(), name="subscription_plan"),
    path("status/", SubscriptionStatusView.as_view(), name="subscription_status"),
    path("initiate/", InitiatePaymentView.as_view(), name="subscription_initiate"),
    path("verify/", VerifyPaymentView.as_view(), name="subscription_verify"),
    path("esewa/success/", EsewaSuccessView.as_view(), name="esewa_success"),
    path("esewa/failure/", EsewaFailureView.as_view(), name="esewa_failure"),
]
