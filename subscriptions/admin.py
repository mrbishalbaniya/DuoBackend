from decimal import Decimal

from django.contrib import admin, messages

from .models import SubscriptionPayment, SubscriptionPlan, Wallet, WalletTopUp, WalletTransaction
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
                description="Admin test credit",
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
