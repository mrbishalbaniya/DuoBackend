import json
from decimal import Decimal

from django.contrib import admin, messages
from django.utils.html import escape
from django.utils.safestring import mark_safe

from .models import (
    GiftCard,
    SubscriptionPayment,
    SubscriptionPlan,
    Wallet,
    WalletTopUp,
    WalletTransaction,
)
from .services import activate_payment
from .wallet_services import credit_wallet

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "plan_id",
        "price_label",
        "badge",
        "duration_days",
        "amount",
        "currency",
        "is_default",
        "is_active",
        "sort_order",
    )
    list_editable = ("amount", "duration_days", "badge", "is_active", "is_default", "sort_order")
    list_filter = ("feature", "is_active", "badge")
    search_fields = ("name", "plan_id", "description")
    ordering = ("sort_order", "duration_days")
    readonly_fields = ("created_at", "updated_at", "price_label")
    fieldsets = (
        (
            "Who liked you package",
            {
                "fields": (
                    "plan_id",
                    "name",
                    "description",
                    "feature",
                ),
            },
        ),
        (
            "Pricing",
            {
                "fields": (
                    "amount",
                    "currency",
                    "duration_days",
                    "badge",
                    "price_label",
                ),
            },
        ),
        (
            "Visibility",
            {
                "fields": (
                    "is_active",
                    "is_default",
                    "sort_order",
                ),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        if obj.is_default:
            SubscriptionPlan.objects.filter(
                feature=obj.feature,
                is_default=True,
            ).exclude(pk=obj.pk).update(is_default=False)
        super().save_model(request, obj, form, change)


@admin.register(SubscriptionPayment)
class SubscriptionPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_uuid",
        "user",
        "plan_id",
        "total_amount",
        "status",
        "paid_at",
        "expires_at",
        "created_at",
    )
    list_filter = ("status", "plan_id")
    search_fields = ("transaction_uuid", "user__username", "user__email", "esewa_ref_id")
    readonly_fields = ("created_at", "updated_at")
    actions = ("activate_subscriptions",)

    @admin.action(description="Activate selected subscriptions")
    def activate_subscriptions(self, request, queryset):
        activated = 0
        for payment in queryset:
            if payment.status != SubscriptionPayment.STATUS_COMPLETE:
                continue
            if payment.paid_at and payment.expires_at:
                continue
            activate_payment(payment)
            activated += 1

        if activated:
            self.message_user(
                request,
                f"Activated {activated} subscription(s). Premium access is now enabled.",
                messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                "No subscriptions were activated. Select completed payments missing expiry dates.",
                messages.WARNING,
            )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        if (
            obj.status == SubscriptionPayment.STATUS_COMPLETE
            and (not obj.paid_at or not obj.expires_at)
        ):
            activate_payment(obj)
            self.message_user(
                request,
                f"Premium activated until {obj.expires_at:%b %d, %Y %I:%M %p}.",
                messages.SUCCESS,
            )


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "currency", "updated_at")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("created_at", "updated_at")
    actions = ("add_test_credit",)

    @admin.action(description="Add NPR 500 test credit")
    def add_test_credit(self, request, queryset):
        for wallet in queryset:
            credit_wallet(
                wallet.user,
                Decimal("500"),
                tx_type=WalletTransaction.TYPE_ADJUSTMENT,
                description="Admin test credit",
                payment_method="",
            )
        self.message_user(request, f"Credited {queryset.count()} wallet(s).", messages.SUCCESS)


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ("wallet", "type", "amount", "balance_after", "description", "created_at")
    list_filter = ("type",)
    search_fields = ("wallet__user__username", "description", "reference_id")
    readonly_fields = ("created_at",)


@admin.register(WalletTopUp)
class WalletTopUpAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_uuid",
        "user",
        "total_amount",
        "status",
        "paid_at",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("transaction_uuid", "user__username", "esewa_ref_id")
    readonly_fields = ("created_at", "updated_at")


@admin.register(GiftCard)
class GiftCardAdmin(admin.ModelAdmin):
    """Create a gift card by picking an amount (and optionally a note or
    expiry) and clicking Save — the code is generated automatically and
    shown exactly once in the success message. It is never stored or
    displayed again after that, only its hash is kept, so copy it from the
    message before navigating away."""

    list_display = (
        "code_last4",
        "amount",
        "status",
        "redeemed_by",
        "redeemed_at",
        "expires_at",
        "created_by",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = (
        "code_last4",
        "note",
        "redeemed_by__username",
        "redeemed_by__email",
        "created_by__username",
    )
    readonly_fields = (
        "code_last4",
        "status",
        "redeemed_by",
        "redeemed_at",
        "created_by",
        "created_at",
        "updated_at",
    )
    fields = (
        "amount",
        "note",
        "expires_at",
        "code_last4",
        "status",
        "redeemed_by",
        "redeemed_at",
        "created_by",
        "created_at",
        "updated_at",
    )

    def has_change_permission(self, request, obj=None):
        # Amount/status/etc are never edited after creation — a card is
        # either unused, redeemed, or revoked (via the "Revoke" action
        # below). Editing an issued card's amount after the fact would be
        # confusing at best and a bookkeeping hazard at worst.
        return False

    def save_model(self, request, obj, form, change):
        if obj.pk is None:
            plain_code = None
            for _ in range(5):
                candidate = GiftCard.generate_plain_code()
                code_hash = GiftCard.hash_code(candidate)
                if not GiftCard.objects.filter(code_hash=code_hash).exists():
                    plain_code = candidate
                    obj.code_hash = code_hash
                    obj.code_last4 = candidate[-4:]
                    break
            if plain_code is None:
                raise RuntimeError("Could not generate a unique gift card code. Try again.")
            obj.created_by = request.user
            self._pending_code = plain_code
        super().save_model(request, obj, form, change)

    def response_add(self, request, obj, post_url_continue=None):
        code = getattr(self, "_pending_code", None)
        if code:
            # An inline onclick= attribute, not a <script> tag: this portal's
            # message/toast is rendered by inserting the message HTML via
            # JS (innerHTML), and scripts inserted that way are inert per
            # browser spec — they silently never run. An attribute-based
            # handler still fires normally either way.
            onclick = (
                "var b=this;"
                "navigator.clipboard.writeText(" + json.dumps(code) + ").then(function(){"
                "var t=b.textContent;b.textContent='Copied!';"
                "setTimeout(function(){b.textContent=t;},1500);"
                "});"
            )
            html = (
                f"Gift card created for <strong>{obj.amount:.0f}</strong> coins. "
                "Code (shown once — copy it now, it will not be shown again): "
                f"<code style='font-size:1.1em;letter-spacing:0.05em'>{escape(code)}</code> "
                f"<button type='button' onclick='{escape(onclick)}' "
                "style='margin-left:8px;padding:2px 10px;border-radius:6px;"
                "border:1px solid currentColor;background:transparent;cursor:pointer;"
                "font-size:0.85em'>Copy</button>"
            )
            self.message_user(request, mark_safe(html), messages.SUCCESS)
        return super().response_add(request, obj, post_url_continue)

    actions = ("revoke_cards",)

    @admin.action(description="Revoke selected unused gift cards")
    def revoke_cards(self, request, queryset):
        updated = queryset.filter(status=GiftCard.STATUS_UNUSED).update(status=GiftCard.STATUS_REVOKED)
        self.message_user(request, f"Revoked {updated} gift card(s).", messages.SUCCESS)
