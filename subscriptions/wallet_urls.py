from django.urls import path

from .views import (
    WalletPurchaseView,
    WalletTopUpInitiateView,
    WalletTransactionDetailView,
    WalletTransactionListView,
    WalletView,
)

urlpatterns = [
    path("", WalletView.as_view(), name="wallet"),
    path("transactions/", WalletTransactionListView.as_view(), name="wallet_transactions"),
    path(
        "transactions/<int:transaction_id>/",
        WalletTransactionDetailView.as_view(),
        name="wallet_transaction_detail",
    ),
    path("topup/initiate/", WalletTopUpInitiateView.as_view(), name="wallet_topup_initiate"),
    path("purchase/", WalletPurchaseView.as_view(), name="wallet_purchase"),
]
