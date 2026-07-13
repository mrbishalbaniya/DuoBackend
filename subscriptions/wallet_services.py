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

MIN_TOP_UP_AMOUNT = Decimal("100")
MAX_TOP_UP_AMOUNT = Decimal("500000")
TOP_UP_PRESETS = [500, 1000, 2000, 5000]


class InsufficientWalletBalance(Exception):
    def __init__(self, balance: Decimal, required: Decimal):
        self.balance = balance
        self.required = required
        super().__init__(
            f"Insufficient wallet balance. You have NPR {balance:.0f} but need NPR {required:.0f}."
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
            "type",
            "amount",
            "balance_after",
            "description",
            "reference_id",
            "created_at",
        )
    )
    return {
        "balance": int(wallet.balance),
        "currency": wallet.currency,
        "top_up_presets": TOP_UP_PRESETS,
        "transactions": transactions,
    }


def _record_transaction(
    wallet: Wallet,
    *,
    tx_type: str,
    amount: Decimal,
    balance_after: Decimal,
    description: str,
    reference_id: str = "",
) -> WalletTransaction:
    return WalletTransaction.objects.create(
        wallet=wallet,
        type=tx_type,
        amount=amount,
        balance_after=balance_after,
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
        )
    return wallet


def debit_wallet(
    user,
    amount: Decimal,
    *,
    tx_type: str = WalletTransaction.TYPE_PURCHASE,
    description: str = "",
    reference_id: str = "",
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
        )
    return wallet


def create_topup_request(user, amount: int | Decimal) -> tuple[WalletTopUp, dict]:
    total = Decimal(str(amount))
    if total < MIN_TOP_UP_AMOUNT:
        raise ValueError(f"Minimum top-up is NPR {MIN_TOP_UP_AMOUNT:.0f}.")
    if total > MAX_TOP_UP_AMOUNT:
        raise ValueError(f"Maximum top-up is NPR {MAX_TOP_UP_AMOUNT:.0f}.")

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
            description="Wallet top-up via eSewa",
            reference_id=locked.transaction_uuid,
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
            description=f"Purchased {plan['name']}",
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
