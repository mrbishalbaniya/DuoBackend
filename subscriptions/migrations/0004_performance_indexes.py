from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("subscriptions", "0003_subscriptionpayment_payment_source_wallet_and_more"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="subscriptionplan",
            index=models.Index(
                fields=["feature", "is_active", "is_default"],
                name="subplan_feature_active_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="wallettransaction",
            index=models.Index(
                fields=["wallet", "-created_at"],
                name="wallet_tx_wallet_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="subscriptionpayment",
            index=models.Index(
                fields=["user", "status", "-expires_at"],
                name="subpay_user_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="subscriptionpayment",
            index=models.Index(
                fields=["status", "-created_at"],
                name="subpay_status_created_idx",
            ),
        ),
    ]
