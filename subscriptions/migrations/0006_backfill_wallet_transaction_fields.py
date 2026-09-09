from django.db import migrations


def backfill(apps, schema_editor):
    WalletTransaction = apps.get_model("subscriptions", "WalletTransaction")
    for txn in WalletTransaction.objects.filter(total_amount=0):
        txn.total_amount = abs(txn.amount)
        if not txn.payment_method:
            txn.payment_method = "esewa" if txn.type == "top_up" else "wallet"
        txn.save(update_fields=["total_amount", "payment_method"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("subscriptions", "0005_wallet_transaction_status_payment_method"),
    ]

    operations = [
        migrations.RunPython(backfill, noop),
    ]
