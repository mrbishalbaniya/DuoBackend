"""Duo Premium plan definitions and eSewa payment helpers."""

import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from .esewa import _format_amount, generate_payment_signature
from .models import SubscriptionPayment, SubscriptionPlan

DEFAULT_PLAN_ID = "duo_premium_30d"

FALLBACK_PLANS = [
    {
        "plan_id": "duo_premium_7d",
        "name": "7-Day Pass",
        "description": "Unlock Liked you for one week.",
        "duration_days": 7,
        "amount": 149,
        "badge": None,
    },
    {
        "plan_id": "duo_premium_30d",
        "name": "30-Day Pass",
        "description": "Unlock Liked you for one month.",
        "duration_days": 30,
        "amount": 499,
        "badge": "Popular",
    },
    {
        "plan_id": "duo_premium_90d",
        "name": "90-Day Pass",
        "description": "Best value — three months of Premium.",
        "duration_days": 90,
        "amount": 999,
        "badge": "Best value",
    },
]


def _plan_queryset():
    return SubscriptionPlan.objects.filter(
        feature=SubscriptionPlan.FEATURE_WHO_LIKED_YOU,
        is_active=True,
    )


def _plan_to_dict(plan: SubscriptionPlan | dict) -> dict:
    if isinstance(plan, SubscriptionPlan):
        return {
            "plan_id": plan.plan_id,
            "name": plan.name,
            "description": plan.description,
            "duration_days": plan.duration_days,
            "amount": int(plan.amount),
            "badge": plan.badge or None,
            "currency": plan.currency,
        }

    return {
        **plan,
        "currency": plan.get("currency", "NPR"),
        "badge": plan.get("badge") or None,
    }


def get_default_plan_id() -> str:
    default_plan = (
        _plan_queryset()
        .filter(is_default=True)
        .order_by("sort_order", "duration_days")
        .first()
    )
    if default_plan:
        return default_plan.plan_id

    first_plan = _plan_queryset().order_by("sort_order", "duration_days").first()
    if first_plan:
        return first_plan.plan_id

    return DEFAULT_PLAN_ID


def get_subscription_plans() -> list[dict]:
    plans = list(_plan_queryset())
    if plans:
        return [_plan_to_dict(plan) for plan in plans]

    return [_plan_to_dict(plan) for plan in FALLBACK_PLANS]


def get_subscription_plan(plan_id: str | None = None) -> dict:
    plan = get_plan_by_id(plan_id or get_default_plan_id())
    return {**plan, "currency": plan.get("currency", "NPR")}


def get_plan_by_id(plan_id: str) -> dict:
    try:
        plan = SubscriptionPlan.objects.get(
            plan_id=plan_id,
            feature=SubscriptionPlan.FEATURE_WHO_LIKED_YOU,
            is_active=True,
        )
        return _plan_to_dict(plan)
    except SubscriptionPlan.DoesNotExist:
        pass

    for plan in FALLBACK_PLANS:
        if plan["plan_id"] == plan_id:
            return _plan_to_dict(plan)

    raise ValueError(f"Unknown subscription plan: {plan_id}")


def get_plan_duration_days(plan_id: str) -> int:
    try:
        plan = SubscriptionPlan.objects.get(plan_id=plan_id)
        return plan.duration_days
    except SubscriptionPlan.DoesNotExist:
        return get_plan_by_id(plan_id)["duration_days"]


def get_active_subscription(user):
    if not user or not user.is_authenticated:
        return None

    return (
        SubscriptionPayment.objects.filter(
            user=user,
            status=SubscriptionPayment.STATUS_COMPLETE,
            expires_at__gt=timezone.now(),
        )
        .order_by("-expires_at")
        .first()
    )


def user_has_active_subscription(user) -> bool:
    return get_active_subscription(user) is not None


def create_payment_request(user, plan_id: str | None = None) -> tuple[SubscriptionPayment, dict]:
    plan = get_plan_by_id(plan_id or get_default_plan_id())
    amount = Decimal(str(plan["amount"]))
    tax_amount = Decimal("0")
    service_charge = Decimal("0")
    delivery_charge = Decimal("0")
    total_amount = amount + tax_amount + service_charge + delivery_charge

    timestamp = timezone.now().strftime("%y%m%d-%H%M%S")
    random_suffix = uuid.uuid4().hex[:8]
    transaction_uuid = f"DUO-{timestamp}-{random_suffix}"

    payment = SubscriptionPayment.objects.create(
        user=user,
        plan_id=plan["plan_id"],
        transaction_uuid=transaction_uuid,
        amount=amount,
        tax_amount=tax_amount,
        product_service_charge=service_charge,
        product_delivery_charge=delivery_charge,
        total_amount=total_amount,
        status=SubscriptionPayment.STATUS_PENDING,
    )

    signature = generate_payment_signature(
        total_amount=total_amount,
        transaction_uuid=transaction_uuid,
        product_code=settings.ESEWA_PRODUCT_CODE,
        secret_key=settings.ESEWA_SECRET_KEY,
    )

    form_data = {
        "amount": _format_amount(amount),
        "tax_amount": _format_amount(tax_amount),
        "total_amount": _format_amount(total_amount),
        "transaction_uuid": transaction_uuid,
        "product_code": settings.ESEWA_PRODUCT_CODE,
        "product_service_charge": _format_amount(service_charge),
        "product_delivery_charge": _format_amount(delivery_charge),
        "success_url": settings.ESEWA_SUCCESS_URL,
        "failure_url": settings.ESEWA_FAILURE_URL,
        "signed_field_names": "total_amount,transaction_uuid,product_code",
        "signature": signature,
    }

    return payment, form_data


def activate_payment(payment: SubscriptionPayment, ref_id: str = "", transaction_code: str = "") -> None:
    duration = timedelta(days=get_plan_duration_days(payment.plan_id))
    now = timezone.now()

    active = get_active_subscription(payment.user)
    if active and active.expires_at and active.expires_at > now:
        expires_at = active.expires_at + duration
    else:
        expires_at = now + duration

    payment.status = SubscriptionPayment.STATUS_COMPLETE
    payment.paid_at = now
    payment.expires_at = expires_at
    payment.esewa_ref_id = ref_id or payment.esewa_ref_id
    payment.esewa_transaction_code = transaction_code or payment.esewa_transaction_code
    payment.save(
        update_fields=[
            "status",
            "paid_at",
            "expires_at",
            "esewa_ref_id",
            "esewa_transaction_code",
            "updated_at",
        ]
    )
