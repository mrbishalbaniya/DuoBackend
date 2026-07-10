from rest_framework import serializers

from .models import SubscriptionPayment


class SubscriptionPlanSerializer(serializers.Serializer):
    plan_id = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField()
    currency = serializers.CharField()
    amount = serializers.IntegerField()
    duration_days = serializers.IntegerField()
    badge = serializers.CharField(required=False, allow_null=True)


class EsewaFormSerializer(serializers.Serializer):
    amount = serializers.CharField()
    tax_amount = serializers.CharField()
    total_amount = serializers.CharField()
    transaction_uuid = serializers.CharField()
    product_code = serializers.CharField()
    product_service_charge = serializers.CharField()
    product_delivery_charge = serializers.CharField()
    success_url = serializers.URLField()
    failure_url = serializers.URLField()
    signed_field_names = serializers.CharField()
    signature = serializers.CharField()


class InitiatePaymentResponseSerializer(serializers.Serializer):
    payment_url = serializers.URLField()
    transaction_uuid = serializers.CharField()
    form = EsewaFormSerializer()


class SubscriptionStatusSerializer(serializers.Serializer):
    is_premium = serializers.BooleanField()
    expires_at = serializers.DateTimeField(allow_null=True)
    plan = SubscriptionPlanSerializer()


class SubscriptionPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPayment
        fields = [
            "transaction_uuid",
            "total_amount",
            "status",
            "payment_source",
            "paid_at",
            "expires_at",
            "created_at",
        ]


class WalletTransactionSerializer(serializers.Serializer):
    type = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    balance_after = serializers.DecimalField(max_digits=12, decimal_places=2)
    description = serializers.CharField()
    reference_id = serializers.CharField()
    created_at = serializers.DateTimeField()


class WalletSerializer(serializers.Serializer):
    balance = serializers.IntegerField()
    currency = serializers.CharField()
    top_up_presets = serializers.ListField(child=serializers.IntegerField())
    transactions = WalletTransactionSerializer(many=True)


class WalletPurchaseResponseSerializer(serializers.Serializer):
    is_premium = serializers.BooleanField()
    expires_at = serializers.DateTimeField()
    balance = serializers.IntegerField()
    plan = SubscriptionPlanSerializer()
