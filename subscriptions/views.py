import logging

from django.conf import settings
from django.http import HttpResponseRedirect
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .esewa import check_transaction_status, decode_callback_payload, verify_response_signature
from .models import SubscriptionPayment
from .serializers import (
    InitiatePaymentResponseSerializer,
    SubscriptionPlanSerializer,
    SubscriptionStatusSerializer,
)
from .services import (
    activate_payment,
    create_payment_request,
    get_active_subscription,
    get_subscription_plan,
    get_subscription_plans,
    user_has_active_subscription,
)

logger = logging.getLogger(__name__)


class SubscriptionPlanView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Subscriptions"],
        summary="List Duo Premium plans",
        responses={200: SubscriptionPlanSerializer(many=True)},
    )
    def get(self, request):
        return Response(get_subscription_plans())


class SubscriptionStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Subscriptions"],
        summary="Get current subscription status",
        responses={200: SubscriptionStatusSerializer},
    )
    def get(self, request):
        active = get_active_subscription(request.user)
        active_plan = get_subscription_plan(active.plan_id) if active else get_subscription_plan()
        return Response(
            {
                "is_premium": active is not None,
                "expires_at": active.expires_at if active else None,
                "plan": active_plan,
            }
        )


class InitiatePaymentView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Subscriptions"],
        summary="Initiate eSewa payment for Duo Premium",
        responses={200: InitiatePaymentResponseSerializer},
    )
    def post(self, request):
        plan_id = request.data.get("plan_id")
        if user_has_active_subscription(request.user):
            return Response(
                {"detail": "You already have an active Duo Premium subscription."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payment, form_data = create_payment_request(request.user, plan_id=plan_id)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "payment_url": settings.ESEWA_FORM_URL,
                "transaction_uuid": payment.transaction_uuid,
                "form": form_data,
            }
        )


class VerifyPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Subscriptions"],
        summary="Verify pending eSewa payment via status check API",
    )
    def post(self, request):
        transaction_uuid = request.data.get("transaction_uuid")
        if not transaction_uuid:
            return Response(
                {"detail": "transaction_uuid is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payment = SubscriptionPayment.objects.get(
                transaction_uuid=transaction_uuid,
                user=request.user,
            )
        except SubscriptionPayment.DoesNotExist:
            return Response({"detail": "Payment not found."}, status=status.HTTP_404_NOT_FOUND)

        if payment.is_active:
            return Response({"status": "COMPLETE", "is_premium": True})

        status_data = check_transaction_status(
            product_code=settings.ESEWA_PRODUCT_CODE,
            total_amount=payment.total_amount,
            transaction_uuid=payment.transaction_uuid,
        )

        esewa_status = status_data.get("status")
        if esewa_status == "COMPLETE":
            activate_payment(
                payment,
                ref_id=str(status_data.get("ref_id") or ""),
            )
            return Response({"status": "COMPLETE", "is_premium": True})

        if esewa_status in {"CANCELED", "NOT_FOUND", "FULL_REFUND"}:
            payment.status = SubscriptionPayment.STATUS_CANCELED
            payment.save(update_fields=["status", "updated_at"])

        return Response(
            {
                "status": esewa_status or "PENDING",
                "is_premium": False,
            }
        )


class EsewaSuccessView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(exclude=True)
    def get(self, request):
        return self._handle_callback(request)

    @extend_schema(exclude=True)
    def post(self, request):
        return self._handle_callback(request)

    def _handle_callback(self, request):
        encoded_data = request.GET.get("data") or request.POST.get("data")
        redirect_url = f"{settings.FRONTEND_URL.rstrip('/')}/discover?subscription=failed"

        if not encoded_data:
            return HttpResponseRedirect(redirect_url)

        try:
            payload = decode_callback_payload(encoded_data)
        except (ValueError, TypeError):
            logger.exception("Failed to decode eSewa success payload")
            return HttpResponseRedirect(redirect_url)

        if not verify_response_signature(payload, settings.ESEWA_SECRET_KEY):
            logger.warning("Invalid eSewa success signature for %s", payload.get("transaction_uuid"))
            return HttpResponseRedirect(redirect_url)

        transaction_uuid = payload.get("transaction_uuid")
        if payload.get("status") != "COMPLETE" or not transaction_uuid:
            return HttpResponseRedirect(redirect_url)

        try:
            payment = SubscriptionPayment.objects.get(transaction_uuid=transaction_uuid)
        except SubscriptionPayment.DoesNotExist:
            logger.warning("Unknown eSewa transaction_uuid: %s", transaction_uuid)
            return HttpResponseRedirect(redirect_url)

        activate_payment(
            payment,
            ref_id=str(payload.get("transaction_code") or payload.get("ref_id") or ""),
            transaction_code=str(payload.get("transaction_code") or ""),
        )

        return HttpResponseRedirect(
            f"{settings.FRONTEND_URL.rstrip('/')}/discover?subscription=success&tab=likes-you"
        )


class EsewaFailureView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(exclude=True)
    def get(self, request):
        return self._handle_failure(request)

    @extend_schema(exclude=True)
    def post(self, request):
        return self._handle_failure(request)

    def _handle_failure(self, request):
        encoded_data = request.GET.get("data") or request.POST.get("data")
        transaction_uuid = request.GET.get("transaction_uuid") or request.POST.get("transaction_uuid")

        if encoded_data:
            try:
                payload = decode_callback_payload(encoded_data)
                transaction_uuid = payload.get("transaction_uuid") or transaction_uuid
            except (ValueError, TypeError):
                logger.exception("Failed to decode eSewa failure payload")

        if transaction_uuid:
            SubscriptionPayment.objects.filter(
                transaction_uuid=transaction_uuid,
                status=SubscriptionPayment.STATUS_PENDING,
            ).update(status=SubscriptionPayment.STATUS_FAILED, updated_at=timezone.now())

        return HttpResponseRedirect(
            f"{settings.FRONTEND_URL.rstrip('/')}/discover?subscription=failed&tab=likes-you"
        )
