from django.urls import path, include

from .views import (
    EsewaFailureView,
    EsewaSuccessView,
    InitiatePaymentView,
    StripeCancelView,
    StripeSuccessView,
    StripeWebhookView,
    SubscriptionPlanView,
    SubscriptionStatusView,
    VerifyPaymentView,
)
from .wallet_urls import urlpatterns as wallet_urlpatterns

urlpatterns = [
    path("plan/", SubscriptionPlanView.as_view(), name="subscription_plan"),
    path("status/", SubscriptionStatusView.as_view(), name="subscription_status"),
    path("initiate/", InitiatePaymentView.as_view(), name="subscription_initiate"),
    path("verify/", VerifyPaymentView.as_view(), name="subscription_verify"),
    path("esewa/success/", EsewaSuccessView.as_view(), name="esewa_success"),
    path("esewa/failure/", EsewaFailureView.as_view(), name="esewa_failure"),
    path("stripe/success/", StripeSuccessView.as_view(), name="stripe_success"),
    path("stripe/cancel/", StripeCancelView.as_view(), name="stripe_cancel"),
    path("stripe/webhook/", StripeWebhookView.as_view(), name="stripe_webhook"),
    path("wallet/", include(wallet_urlpatterns)),
]
