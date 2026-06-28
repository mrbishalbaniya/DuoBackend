from django.contrib import admin, messages

from .models import SubscriptionPayment, SubscriptionPlan
from .services import activate_payment

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
