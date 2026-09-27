"""Duo Premium plan definitions (one set per premium feature) and eSewa payment helpers."""

import uuid
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from duo_project.runtime_config import get_integration_settings

from .esewa import _format_amount, generate_payment_signature
from .models import SubscriptionPayment, SubscriptionPlan

FEATURE_WHO_LIKED_YOU = SubscriptionPlan.FEATURE_WHO_LIKED_YOU
FEATURE_VISITED_YOU = SubscriptionPlan.FEATURE_VISITED_YOU
FEATURE_REWIND = SubscriptionPlan.FEATURE_REWIND
FEATURE_UNLIMITED_LIKES = SubscriptionPlan.FEATURE_UNLIMITED_LIKES
FEATURES = SubscriptionPlan.FEATURES
FEATURE_LABELS = dict(SubscriptionPlan.FEATURE_CHOICES)
# Passes bought before plans were split ("all") covered only these two lists.
LEGACY_PASS_FEATURES = (FEATURE_WHO_LIKED_YOU, FEATURE_VISITED_YOU)

DEFAULT_PLAN_IDS = {
    FEATURE_WHO_LIKED_YOU: "duo_premium_30d",
    FEATURE_VISITED_YOU: "visited_you_30d",
    FEATURE_REWIND: "rewind_30d",
    FEATURE_UNLIMITED_LIKES: "unlimited_likes_30d",
}
# Kept for callers that predate per-feature plans.
DEFAULT_PLAN_ID = DEFAULT_PLAN_IDS[FEATURE_WHO_LIKED_YOU]

# Served only when the database has no active plans for a feature.
FALLBACK_PLANS = {
    FEATURE_WHO_LIKED_YOU: [
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
    ],
    FEATURE_VISITED_YOU: [
        {
            "plan_id": "visited_you_7d",
            "name": "7-Day Visitors Pass",
            "description": "See who visited your profile for one week.",
            "duration_days": 7,
            "amount": 149,
            "badge": None,
        },
        {
            "plan_id": "visited_you_30d",
            "name": "30-Day Visitors Pass",
            "description": "See who visited your profile for one month.",
            "duration_days": 30,
            "amount": 499,
            "badge": "Popular",
        },
        {
            "plan_id": "visited_you_90d",
            "name": "90-Day Visitors Pass",
            "description": "Best value: three months of profile visitors.",
            "duration_days": 90,
            "amount": 999,
            "badge": "Best value",
        },
    ],
    FEATURE_REWIND: [
        {
            "plan_id": "rewind_7d",
            "name": "7-Day Rewind",
            "description": "Undo swipes for one week.",
            "duration_days": 7,
            "amount": 99,
            "badge": None,
        },
        {
            "plan_id": "rewind_30d",
            "name": "30-Day Rewind",
            "description": "Undo swipes for one month.",
            "duration_days": 30,
            "amount": 299,
            "badge": "Popular",
        },
        {
            "plan_id": "rewind_90d",
            "name": "90-Day Rewind",
            "description": "Best value: three months of rewinds.",
            "duration_days": 90,
            "amount": 699,
            "badge": "Best value",
        },
    ],
    FEATURE_UNLIMITED_LIKES: [
        {
            "plan_id": "unlimited_likes_7d",
            "name": "7-Day Unlimited Likes",
            "description": "Like as many people as you want for one week.",
            "duration_days": 7,
            "amount": 199,
            "badge": None,
        },
        {
            "plan_id": "unlimited_likes_30d",
            "name": "30-Day Unlimited Likes",
            "description": "No Like limit for one month.",
            "duration_days": 30,
            "amount": 599,
            "badge": "Popular",
        },
        {
            "plan_id": "unlimited_likes_90d",
            "name": "90-Day Unlimited Likes",
            "description": "Best value: three months without a Like limit.",
            "duration_days": 90,
            "amount": 1299,
            "badge": "Best value",
        },
    ],
}


def normalize_feature(feature: str | None) -> str:
    """Return a valid plan feature, defaulting to "Who liked you"."""
    if not feature:
        return FEATURE_WHO_LIKED_YOU
    if feature not in FEATURES:
        raise ValueError(f"Unknown subscription feature: {feature}")
    return feature


def _plan_queryset(feature: str = FEATURE_WHO_LIKED_YOU):
    return SubscriptionPlan.objects.filter(feature=feature, is_active=True)


def _plan_to_dict(plan: SubscriptionPlan | dict, feature: str | None = None) -> dict:
    if isinstance(plan, SubscriptionPlan):
        return {
            "plan_id": plan.plan_id,
            "name": plan.name,
            "description": plan.description,
            "feature": plan.feature,
            "feature_label": FEATURE_LABELS.get(plan.feature, plan.feature),
            "duration_days": plan.duration_days,
            "amount": int(plan.amount),
            "badge": plan.badge or None,
            "currency": plan.currency,
        }

    plan_feature = plan.get("feature") or feature or FEATURE_WHO_LIKED_YOU
    return {
        **plan,
        "feature": plan_feature,
        "feature_label": FEATURE_LABELS.get(plan_feature, plan_feature),
        "currency": plan.get("currency", "NPR"),
        "badge": plan.get("badge") or None,
    }


def get_default_plan_id(feature: str | None = None) -> str:
    feature = normalize_feature(feature)
    default_plan = (
        _plan_queryset(feature)
        .filter(is_default=True)
        .order_by("sort_order", "duration_days")
        .first()
    )
    if default_plan:
        return default_plan.plan_id

    first_plan = _plan_queryset(feature).order_by("sort_order", "duration_days").first()
    if first_plan:
        return first_plan.plan_id

    return DEFAULT_PLAN_IDS[feature]


def get_subscription_plans(feature: str | None = None) -> list[dict]:
    feature = normalize_feature(feature)
    plans = list(_plan_queryset(feature))
    if plans:
        return [_plan_to_dict(plan) for plan in plans]

    return [_plan_to_dict(plan, feature) for plan in FALLBACK_PLANS[feature]]


def get_subscription_plan(plan_id: str | None = None, feature: str | None = None) -> dict:
    plan = get_plan_by_id(plan_id or get_default_plan_id(feature))
    return {**plan, "currency": plan.get("currency", "NPR")}


def get_plan_by_id(plan_id: str) -> dict:
    """Look up an active plan of any feature; the plan decides what it unlocks."""
    try:
        plan = SubscriptionPlan.objects.get(plan_id=plan_id, is_active=True)
        return _plan_to_dict(plan)
    except SubscriptionPlan.DoesNotExist:
        pass

    for feature, plans in FALLBACK_PLANS.items():
        for plan in plans:
            if plan["plan_id"] == plan_id:
                return _plan_to_dict(plan, feature)

    raise ValueError(f"Unknown subscription plan: {plan_id}")


def get_plan_duration_days(plan_id: str) -> int:
    try:
        plan = SubscriptionPlan.objects.get(plan_id=plan_id)
        return plan.duration_days
    except SubscriptionPlan.DoesNotExist:
        return get_plan_by_id(plan_id)["duration_days"]


def get_active_subscription(user, feature: str | None = None):
    """Latest-expiring active pass. With a feature, only passes that unlock it."""
    if not user or not user.is_authenticated:
        return None

    payments = SubscriptionPayment.objects.filter(
        user=user,
        status=SubscriptionPayment.STATUS_COMPLETE,
        expires_at__gt=timezone.now(),
    )
    if feature:
        allowed = [feature]
        if feature in LEGACY_PASS_FEATURES:
            allowed.append(SubscriptionPayment.FEATURE_ALL)
        payments = payments.filter(feature__in=allowed)
    return payments.order_by("-expires_at").first()


def user_has_active_subscription(user, feature: str | None = None) -> bool:
    """True when the user has any active pass, or one unlocking `feature`."""
    return get_active_subscription(user, feature) is not None


def get_feature_access(user) -> dict:
    """Per-feature access summary for the status endpoint."""
    access = {}
    for feature in FEATURES:
        active = get_active_subscription(user, feature)
        access[feature] = {
            "label": FEATURE_LABELS[feature],
            "is_active": active is not None,
            "expires_at": active.expires_at if active else None,
        }
    return access


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
        feature=plan["feature"],
        transaction_uuid=transaction_uuid,
        amount=amount,
        tax_amount=tax_amount,
        product_service_charge=service_charge,
        product_delivery_charge=delivery_charge,
        total_amount=total_amount,
        status=SubscriptionPayment.STATUS_PENDING,
    )

    cfg = get_integration_settings()
    if not cfg.esewa_product_code or not cfg.esewa_secret_key:
        raise ValueError(
            "eSewa is not configured. Set credentials in Admin → Integration settings "
            "or ESEWA_PRODUCT_CODE and ESEWA_SECRET_KEY in the environment."
        )

    signature = generate_payment_signature(
        total_amount=total_amount,
        transaction_uuid=transaction_uuid,
        product_code=cfg.esewa_product_code,
        secret_key=cfg.esewa_secret_key,
    )

    form_data = {
        "amount": _format_amount(amount),
        "tax_amount": _format_amount(tax_amount),
        "total_amount": _format_amount(total_amount),
        "transaction_uuid": transaction_uuid,
        "product_code": cfg.esewa_product_code,
        "product_service_charge": _format_amount(service_charge),
        "product_delivery_charge": _format_amount(delivery_charge),
        "success_url": cfg.esewa_success_url,
        "failure_url": cfg.esewa_failure_url,
        "signed_field_names": "total_amount,transaction_uuid,product_code",
        "signature": signature,
    }

    return payment, form_data


def activate_payment(payment: SubscriptionPayment, ref_id: str = "", transaction_code: str = "") -> None:
    duration = timedelta(days=get_plan_duration_days(payment.plan_id))
    now = timezone.now()

    # Stack onto an existing pass for the same feature only.
    feature = None if payment.feature == SubscriptionPayment.FEATURE_ALL else payment.feature
    active = get_active_subscription(payment.user, feature)
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
