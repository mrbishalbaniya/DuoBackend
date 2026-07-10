import logging

from django.conf import settings
from django.http import HttpResponseRedirect
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from duo_project.runtime_config import get_integration_settings
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .esewa import check_transaction_status, decode_callback_payload, verify_response_signature
from .models import SubscriptionPayment, WalletTopUp
from .serializers import (
    InitiatePaymentResponseSerializer,
    SubscriptionPlanSerializer,
    SubscriptionStatusSerializer,
    WalletPurchaseResponseSerializer,
    WalletSerializer,
)
from .services import (
    activate_payment,
    get_active_subscription,
    get_subscription_plan,
    get_subscription_plans,
)

from .wallet_services import (
    InsufficientWalletBalance,
    activate_topup,
    create_topup_request,
    get_wallet_summary,
    purchase_plan_with_wallet,
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
        summary="Deprecated — use wallet top-up and purchase instead",
        responses={410: None},
    )
    def post(self, request):
        return Response(
            {
                "detail": (
                    "Direct eSewa subscription payments are no longer supported. "
                    "Top up your wallet and purchase a pass from your balance."
                )
            },
            status=status.HTTP_410_GONE,
        )


class WalletView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Wallet"],
        summary="Get wallet balance and recent transactions",
        responses={200: WalletSerializer},
    )
    def get(self, request):
        return Response(get_wallet_summary(request.user))


class WalletTopUpInitiateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Wallet"],
        summary="Initiate eSewa wallet top-up",
        responses={200: InitiatePaymentResponseSerializer},
    )
    def post(self, request):
        amount = request.data.get("amount")
        if amount is None:
            return Response(
                {"detail": "amount is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            amount_int = int(amount)
        except (TypeError, ValueError):
            return Response(
                {"detail": "amount must be a whole number."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            topup, form_data = create_topup_request(request.user, amount_int)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        cfg = get_integration_settings()
        return Response(
            {
                "payment_url": cfg.esewa_form_url,
                "transaction_uuid": topup.transaction_uuid,
                "form": form_data,
            }
        )


class WalletPurchaseView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Wallet"],
        summary="Purchase a premium pass using wallet balance",
        responses={200: WalletPurchaseResponseSerializer},
    )
    def post(self, request):
        plan_id = request.data.get("plan_id")
        try:
            payment = purchase_plan_with_wallet(request.user, plan_id=plan_id)
        except InsufficientWalletBalance as exc:
            return Response(
                {
                    "detail": str(exc),
                    "balance": int(exc.balance),
                    "required": int(exc.required),
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        active_plan = get_subscription_plan(payment.plan_id)
        wallet = get_wallet_summary(request.user, limit=0)
        return Response(
            {
                "is_premium": True,
                "expires_at": payment.expires_at,
                "balance": wallet["balance"],
                "plan": active_plan,
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
            topup = WalletTopUp.objects.get(
                transaction_uuid=transaction_uuid,
                user=request.user,
            )
        except WalletTopUp.DoesNotExist:
            topup = None

        if topup:
            if topup.status == WalletTopUp.STATUS_COMPLETE:
                wallet = get_wallet_summary(request.user, limit=0)
                return Response({"status": "COMPLETE", "balance": wallet["balance"]})

            cfg = get_integration_settings()
            status_data = check_transaction_status(
                product_code=cfg.esewa_product_code,
                total_amount=topup.total_amount,
                transaction_uuid=topup.transaction_uuid,
            )

            esewa_status = status_data.get("status")
            if esewa_status == "COMPLETE":
                activate_topup(topup, ref_id=str(status_data.get("ref_id") or ""))
                wallet = get_wallet_summary(request.user, limit=0)
                return Response({"status": "COMPLETE", "balance": wallet["balance"]})

            if esewa_status in {"CANCELED", "NOT_FOUND", "FULL_REFUND"}:
                topup.status = WalletTopUp.STATUS_CANCELED
                topup.save(update_fields=["status", "updated_at"])

            wallet = get_wallet_summary(request.user, limit=0)
            return Response(
                {
                    "status": esewa_status or "PENDING",
                    "balance": wallet["balance"],
                }
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

        cfg = get_integration_settings()
        status_data = check_transaction_status(
            product_code=cfg.esewa_product_code,
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
        frontend = settings.FRONTEND_URL.rstrip("/")
        redirect_url = f"{frontend}/wallet?wallet=failed"

        if not encoded_data:
            return HttpResponseRedirect(redirect_url)

        try:
            payload = decode_callback_payload(encoded_data)
        except (ValueError, TypeError):
            logger.exception("Failed to decode eSewa success payload")
            return HttpResponseRedirect(redirect_url)

        cfg = get_integration_settings()
        if not verify_response_signature(payload, cfg.esewa_secret_key):
            logger.warning("Invalid eSewa success signature for %s", payload.get("transaction_uuid"))
            return HttpResponseRedirect(redirect_url)

        transaction_uuid = payload.get("transaction_uuid")
        if payload.get("status") != "COMPLETE" or not transaction_uuid:
            return HttpResponseRedirect(redirect_url)

        ref_id = str(payload.get("transaction_code") or payload.get("ref_id") or "")
        transaction_code = str(payload.get("transaction_code") or "")

        try:
            topup = WalletTopUp.objects.get(transaction_uuid=transaction_uuid)
            activate_topup(topup, ref_id=ref_id, transaction_code=transaction_code)
            return HttpResponseRedirect(f"{frontend}/wallet?wallet=success")
        except WalletTopUp.DoesNotExist:
            pass

        try:
            payment = SubscriptionPayment.objects.get(transaction_uuid=transaction_uuid)
        except SubscriptionPayment.DoesNotExist:
            logger.warning("Unknown eSewa transaction_uuid: %s", transaction_uuid)
            return HttpResponseRedirect(redirect_url)

        activate_payment(payment, ref_id=ref_id, transaction_code=transaction_code)

        return HttpResponseRedirect(
            f"{frontend}/discover?subscription=success&tab=likes-you"
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
            WalletTopUp.objects.filter(
                transaction_uuid=transaction_uuid,
                status=WalletTopUp.STATUS_PENDING,
            ).update(status=WalletTopUp.STATUS_FAILED, updated_at=timezone.now())

            SubscriptionPayment.objects.filter(
                transaction_uuid=transaction_uuid,
                status=SubscriptionPayment.STATUS_PENDING,
            ).update(status=SubscriptionPayment.STATUS_FAILED, updated_at=timezone.now())

        frontend = settings.FRONTEND_URL.rstrip("/")
        if transaction_uuid and str(transaction_uuid).startswith("WLT-"):
            return HttpResponseRedirect(f"{frontend}/wallet?wallet=failed")
        return HttpResponseRedirect(
            f"{frontend}/discover?subscription=failed&tab=likes-you"
        )
