"""Wallet balance, top-ups, and premium purchases."""

import uuid
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from duo_project.runtime_config import get_integration_settings

from .esewa import _format_amount, generate_payment_signature
from .models import SubscriptionPayment, Wallet, WalletTopUp, WalletTransaction
from .services import (
    activate_payment,
    get_default_plan_id,
    get_plan_by_id,
    user_has_active_subscription,
)

MIN_TOP_UP_AMOUNT = Decimal("50")
MAX_TOP_UP_AMOUNT = Decimal("500000")

# 1 NPR paid via eSewa credits 1 Duo Coin.
COIN_PACKS = [
    {"id": "coins_50", "coins": 50, "price_npr": 50, "label": "50 Coins"},
    {"id": "coins_100", "coins": 100, "price_npr": 100, "label": "100 Coins"},
    {"id": "coins_250", "coins": 250, "price_npr": 250, "label": "250 Coins"},
    {"id": "coins_500", "coins": 500, "price_npr": 500, "label": "500 Coins"},
    {"id": "coins_1000", "coins": 1000, "price_npr": 1000, "label": "1,000 Coins"},
    {"id": "coins_2000", "coins": 2000, "price_npr": 2000, "label": "2,000 Coins"},
    {"id": "coins_3000", "coins": 3000, "price_npr": 3000, "label": "3,000 Coins"},
    {"id": "coins_5000", "coins": 5000, "price_npr": 5000, "label": "5,000 Coins"},
]
TOP_UP_PRESETS = [pack["coins"] for pack in COIN_PACKS]


class InsufficientWalletBalance(Exception):
    def __init__(self, balance: Decimal, required: Decimal):
        self.balance = balance
        self.required = required
        super().__init__(
            f"Insufficient coins. You have {balance:.0f} coins but need {required:.0f}."
        )


def get_or_create_wallet(user) -> Wallet:
    wallet, _ = Wallet.objects.get_or_create(user=user, defaults={"balance": Decimal("0")})
    return wallet


def get_wallet_balance(user) -> Decimal:
    return get_or_create_wallet(user).balance


def get_wallet_summary(user, *, limit: int = 20) -> dict:
    wallet = get_or_create_wallet(user)
    transactions = list(
        wallet.transactions.order_by("-created_at")[:limit].values(
            "id",
            "type",
            "amount",
            "balance_after",
            "total_amount",
            "status",
            "payment_method",
            "description",
            "reference_id",
            "created_at",
            "updated_at",
        )
    )
    return {
        "balance": int(wallet.balance),
        "coins": int(wallet.balance),
        "currency": "COIN",
        "top_up_presets": TOP_UP_PRESETS,
        "coin_packs": COIN_PACKS,
        "transactions": transactions,
    }


def list_wallet_transactions(
    user,
    *,
    date_from=None,
    date_to=None,
    payment_method: str = "",
    before_id: int | None = None,
    limit: int = 20,
) -> dict:
    wallet = get_or_create_wallet(user)
    qs = wallet.transactions.order_by("-created_at", "-id")

    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)
    if payment_method:
        qs = qs.filter(payment_method=payment_method)
    if before_id:
        qs = qs.filter(id__lt=before_id)

    limit = max(1, min(limit, 100))
    rows = list(
        qs[:limit].values(
            "id",
            "type",
            "amount",
            "balance_after",
            "total_amount",
            "status",
            "payment_method",
            "description",
            "reference_id",
            "created_at",
            "updated_at",
        )
    )
    has_more = len(rows) == limit
    return {
        "results": rows,
        "has_more": has_more,
        "next_before": rows[-1]["id"] if has_more and rows else None,
    }


def get_wallet_transaction(user, transaction_id: int) -> WalletTransaction | None:
    wallet = get_or_create_wallet(user)
    return wallet.transactions.filter(id=transaction_id).first()


def _record_transaction(
    wallet: Wallet,
    *,
    tx_type: str,
    amount: Decimal,
    balance_after: Decimal,
    description: str,
    reference_id: str = "",
    total_amount: Decimal = Decimal("0"),
    payment_method: str = "",
    status: str = WalletTransaction.STATUS_COMPLETE,
) -> WalletTransaction:
    return WalletTransaction.objects.create(
        wallet=wallet,
        type=tx_type,
        amount=amount,
        balance_after=balance_after,
        total_amount=total_amount,
        payment_method=payment_method,
        status=status,
        description=description,
        reference_id=reference_id,
    )


def credit_wallet(
    user,
    amount: Decimal,
    *,
    tx_type: str = WalletTransaction.TYPE_TOP_UP,
    description: str = "",
    reference_id: str = "",
    total_amount: Decimal | None = None,
    payment_method: str = WalletTransaction.PAYMENT_METHOD_ESEWA,
) -> Wallet:
    if amount <= 0:
        raise ValueError("Credit amount must be positive.")

    with transaction.atomic():
        wallet, _ = Wallet.objects.select_for_update().get_or_create(
            user=user,
            defaults={"balance": Decimal("0")},
        )
        wallet.balance += amount
        wallet.save(update_fields=["balance", "updated_at"])
        _record_transaction(
            wallet,
            tx_type=tx_type,
            amount=amount,
            balance_after=wallet.balance,
            description=description,
            reference_id=reference_id,
            total_amount=total_amount if total_amount is not None else amount,
            payment_method=payment_method,
        )
    return wallet


def debit_wallet(
    user,
    amount: Decimal,
    *,
    tx_type: str = WalletTransaction.TYPE_PURCHASE,
    description: str = "",
    reference_id: str = "",
    total_amount: Decimal | None = None,
    payment_method: str = WalletTransaction.PAYMENT_METHOD_WALLET,
) -> Wallet:
    if amount <= 0:
        raise ValueError("Debit amount must be positive.")

    with transaction.atomic():
        wallet, _ = Wallet.objects.select_for_update().get_or_create(
            user=user,
            defaults={"balance": Decimal("0")},
        )
        if wallet.balance < amount:
            raise InsufficientWalletBalance(wallet.balance, amount)
        wallet.balance -= amount
        wallet.save(update_fields=["balance", "updated_at"])
        _record_transaction(
            wallet,
            tx_type=tx_type,
            amount=-amount,
            balance_after=wallet.balance,
            description=description,
            reference_id=reference_id,
            total_amount=total_amount if total_amount is not None else amount,
            payment_method=payment_method,
        )
    return wallet


def create_topup_request(user, amount: int | Decimal) -> tuple[WalletTopUp, dict]:
    total = Decimal(str(amount))
    if total < MIN_TOP_UP_AMOUNT:
        raise ValueError(f"Minimum coin pack is {MIN_TOP_UP_AMOUNT:.0f} coins (NPR {MIN_TOP_UP_AMOUNT:.0f}).")
    if total > MAX_TOP_UP_AMOUNT:
        raise ValueError(f"Maximum coin pack is {MAX_TOP_UP_AMOUNT:.0f} coins (NPR {MAX_TOP_UP_AMOUNT:.0f}).")

    tax_amount = Decimal("0")
    service_charge = Decimal("0")
    delivery_charge = Decimal("0")
    total_amount = total + tax_amount + service_charge + delivery_charge

    timestamp = timezone.now().strftime("%y%m%d-%H%M%S")
    random_suffix = uuid.uuid4().hex[:8]
    transaction_uuid = f"WLT-{timestamp}-{random_suffix}"

    topup = WalletTopUp.objects.create(
        user=user,
        transaction_uuid=transaction_uuid,
        amount=total,
        tax_amount=tax_amount,
        product_service_charge=service_charge,
        product_delivery_charge=delivery_charge,
        total_amount=total_amount,
        status=WalletTopUp.STATUS_PENDING,
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
        "amount": _format_amount(total),
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

    return topup, form_data


def activate_topup(
    topup: WalletTopUp,
    ref_id: str = "",
    transaction_code: str = "",
) -> None:
    with transaction.atomic():
        locked = WalletTopUp.objects.select_for_update().get(pk=topup.pk)
        if locked.status == WalletTopUp.STATUS_COMPLETE:
            return

        now = timezone.now()
        locked.status = WalletTopUp.STATUS_COMPLETE
        locked.paid_at = now
        locked.esewa_ref_id = ref_id or locked.esewa_ref_id
        locked.esewa_transaction_code = transaction_code or locked.esewa_transaction_code
        locked.save(
            update_fields=[
                "status",
                "paid_at",
                "esewa_ref_id",
                "esewa_transaction_code",
                "updated_at",
            ]
        )

        credit_wallet(
            locked.user,
            locked.total_amount,
            tx_type=WalletTransaction.TYPE_TOP_UP,
            description=f"Purchased {int(locked.total_amount):,} coins via eSewa",
            reference_id=locked.transaction_uuid,
            total_amount=locked.total_amount,
            payment_method=WalletTransaction.PAYMENT_METHOD_ESEWA,
        )


def purchase_plan_with_wallet(user, plan_id: str | None = None) -> SubscriptionPayment:
    if user_has_active_subscription(user):
        raise ValueError("You already have an active Duo Premium pass.")

    plan = get_plan_by_id(plan_id or get_default_plan_id())
    amount = Decimal(str(plan["amount"]))

    with transaction.atomic():
        debit_wallet(
            user,
            amount,
            tx_type=WalletTransaction.TYPE_PURCHASE,
            description=f"{plan['name']} · {int(amount):,} coins",
            reference_id=plan["plan_id"],
        )

        timestamp = timezone.now().strftime("%y%m%d-%H%M%S")
        random_suffix = uuid.uuid4().hex[:8]
        transaction_uuid = f"WALLET-{timestamp}-{random_suffix}"

        payment = SubscriptionPayment.objects.create(
            user=user,
            plan_id=plan["plan_id"],
            transaction_uuid=transaction_uuid,
            amount=amount,
            tax_amount=Decimal("0"),
            product_service_charge=Decimal("0"),
            product_delivery_charge=Decimal("0"),
            total_amount=amount,
            status=SubscriptionPayment.STATUS_PENDING,
            payment_source=SubscriptionPayment.SOURCE_WALLET,
        )
        activate_payment(payment)

    return payment
