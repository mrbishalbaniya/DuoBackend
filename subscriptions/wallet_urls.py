from django.urls import path

from .views import WalletPurchaseView, WalletTopUpInitiateView, WalletView

urlpatterns = [
    path("", WalletView.as_view(), name="wallet"),
    path("topup/initiate/", WalletTopUpInitiateView.as_view(), name="wallet_topup_initiate"),
    path("purchase/", WalletPurchaseView.as_view(), name="wallet_purchase"),
]
