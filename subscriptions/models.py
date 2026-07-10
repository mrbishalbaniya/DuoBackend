from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class SubscriptionPlan(models.Model):
    FEATURE_WHO_LIKED_YOU = "who_liked_you"

    FEATURE_CHOICES = [
        (FEATURE_WHO_LIKED_YOU, "Who liked you"),
    ]

    BADGE_CHOICES = [
        ("", "None"),
        ("Popular", "Popular"),
        ("Best value", "Best value"),
    ]

    plan_id = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    feature = models.CharField(
        max_length=32,
        choices=FEATURE_CHOICES,
        default=FEATURE_WHO_LIKED_YOU,
    )
    duration_days = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    currency = models.CharField(max_length=8, default="NPR")
    badge = models.CharField(max_length=32, blank=True, default="", choices=BADGE_CHOICES)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(
        default=False,
        help_text="Used when no plan is selected (typically the 30-day pass).",
    )
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "duration_days", "amount"]
        verbose_name = "Who liked you plan"
        verbose_name_plural = "Who liked you plans"

    def __str__(self):
        badge = f" · {self.badge}" if self.badge else ""
        return f"{self.name}{badge} · NPR {self.amount:.0f} / {self.duration_days} days"

    @property
    def price_label(self):
        return f"NPR {self.amount:.0f} / {self.duration_days} days"


class Wallet(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallet",
    )
    balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    currency = models.CharField(max_length=8, default="NPR")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Wallet"
        verbose_name_plural = "Wallets"

    def __str__(self):
        return f"{self.user_id} · {self.currency} {self.balance:.2f}"


class WalletTransaction(models.Model):
    TYPE_TOP_UP = "top_up"
    TYPE_PURCHASE = "purchase"
    TYPE_ADJUSTMENT = "adjustment"

    TYPE_CHOICES = [
        (TYPE_TOP_UP, "Top up"),
        (TYPE_PURCHASE, "Purchase"),
        (TYPE_ADJUSTMENT, "Adjustment"),
    ]

    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=255, blank=True, default="")
    reference_id = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        sign = "+" if self.amount >= 0 else ""
        return f"{self.wallet_id} · {sign}{self.amount} · {self.type}"


class WalletTopUp(models.Model):
    STATUS_PENDING = "pending"
    STATUS_COMPLETE = "complete"
    STATUS_FAILED = "failed"
    STATUS_CANCELED = "canceled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_COMPLETE, "Complete"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELED, "Canceled"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallet_topups",
    )
    transaction_uuid = models.CharField(max_length=64, unique=True, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    product_service_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    product_delivery_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    esewa_ref_id = models.CharField(max_length=64, blank=True, default="")
    esewa_transaction_code = models.CharField(max_length=64, blank=True, default="")
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user_id} · {self.transaction_uuid} · {self.status}"


class SubscriptionPayment(models.Model):
    STATUS_PENDING = "pending"
    STATUS_COMPLETE = "complete"
    STATUS_FAILED = "failed"
    STATUS_CANCELED = "canceled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_COMPLETE, "Complete"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELED, "Canceled"),
    ]

    SOURCE_ESEWA = "esewa"
    SOURCE_WALLET = "wallet"

    SOURCE_CHOICES = [
        (SOURCE_ESEWA, "eSewa"),
        (SOURCE_WALLET, "Wallet"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscription_payments",
    )
    plan_id = models.CharField(max_length=64, default="duo_premium_monthly")
    transaction_uuid = models.CharField(max_length=64, unique=True, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    product_service_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    product_delivery_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    payment_source = models.CharField(
        max_length=16,
        choices=SOURCE_CHOICES,
        default=SOURCE_ESEWA,
    )
    esewa_ref_id = models.CharField(max_length=64, blank=True, default="")
    esewa_transaction_code = models.CharField(max_length=64, blank=True, default="")
    paid_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user_id} · {self.transaction_uuid} · {self.status}"

    @property
    def is_active(self):
        return (
            self.status == self.STATUS_COMPLETE
            and self.expires_at is not None
            and self.expires_at > timezone.now()
        )
