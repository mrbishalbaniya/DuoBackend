from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from subscriptions.models import GiftCard, Wallet, WalletTransaction
from subscriptions.wallet_services import (
    GiftCardAlreadyRedeemed,
    GiftCardExpired,
    GiftCardInvalid,
    redeem_gift_card,
)

User = get_user_model()


def _make_card(amount="100", **kwargs):
    plain = GiftCard.generate_plain_code()
    card = GiftCard.objects.create(
        code_hash=GiftCard.hash_code(plain),
        code_last4=plain[-4:],
        amount=Decimal(amount),
        **kwargs,
    )
    return card, plain


class GiftCardModelTests(APITestCase):
    def test_hash_is_case_and_whitespace_insensitive(self):
        plain = "AB12-CD34-EF56-0102"
        self.assertEqual(GiftCard.hash_code(plain), GiftCard.hash_code(plain.lower()))
        self.assertEqual(GiftCard.hash_code(plain), GiftCard.hash_code(f"  {plain}  "))

    def test_generated_codes_are_unique_and_well_formed(self):
        codes = {GiftCard.generate_plain_code() for _ in range(200)}
        self.assertEqual(len(codes), 200)  # no collisions across 200 draws
        for code in codes:
            parts = code.split("-")
            self.assertEqual(len(parts), 4)
            for part in parts:
                self.assertEqual(len(part), 4)
                int(part, 16)  # must be valid hex

    def test_plaintext_code_is_never_persisted(self):
        card, plain = _make_card()
        card.refresh_from_db()
        # Only the hash and last 4 chars should exist on the row.
        self.assertNotIn(plain, [card.code_hash, card.code_last4])
        self.assertEqual(card.code_hash, GiftCard.hash_code(plain))


@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": ("accounts.authentication.CookieJWTAuthentication",),
        "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
        "DEFAULT_THROTTLE_CLASSES": [],
        "DEFAULT_THROTTLE_RATES": {},
    }
)
class RedeemGiftCardServiceTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="redeemer", email="r@example.com", password="pw12345678")

    def test_successful_redeem_credits_wallet_and_marks_used(self):
        card, plain = _make_card(amount="250")

        wallet, redeemed = redeem_gift_card(self.user, plain)

        self.assertEqual(wallet.balance, Decimal("250"))
        redeemed.refresh_from_db()
        self.assertEqual(redeemed.status, GiftCard.STATUS_REDEEMED)
        self.assertEqual(redeemed.redeemed_by, self.user)
        self.assertIsNotNone(redeemed.redeemed_at)

        tx = wallet.transactions.get()
        self.assertEqual(tx.type, WalletTransaction.TYPE_GIFT_REDEEM)
        self.assertEqual(tx.amount, Decimal("250"))
        self.assertEqual(tx.balance_after, Decimal("250"))

    def test_redeeming_twice_fails_the_second_time(self):
        card, plain = _make_card(amount="100")
        redeem_gift_card(self.user, plain)

        with self.assertRaises(GiftCardAlreadyRedeemed):
            redeem_gift_card(self.user, plain)

        # Balance must reflect exactly one credit, not two.
        wallet = Wallet.objects.get(user=self.user)
        self.assertEqual(wallet.balance, Decimal("100"))
        self.assertEqual(wallet.transactions.count(), 1)

    def test_unknown_code_is_rejected(self):
        with self.assertRaises(GiftCardInvalid):
            redeem_gift_card(self.user, "0000-0000-0000-0000")

    def test_revoked_code_is_rejected(self):
        card, plain = _make_card(status=GiftCard.STATUS_REVOKED)
        with self.assertRaises(GiftCardInvalid):
            redeem_gift_card(self.user, plain)

    def test_expired_code_is_rejected(self):
        card, plain = _make_card(expires_at=timezone.now() - timezone.timedelta(days=1))
        with self.assertRaises(GiftCardExpired):
            redeem_gift_card(self.user, plain)

    def test_code_is_case_insensitive_and_ignores_surrounding_whitespace(self):
        card, plain = _make_card(amount="60")
        wallet, _ = redeem_gift_card(self.user, f"  {plain.lower()}  ")
        self.assertEqual(wallet.balance, Decimal("60"))


@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": ("accounts.authentication.CookieJWTAuthentication",),
        "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
        "DEFAULT_THROTTLE_CLASSES": [],
        "DEFAULT_THROTTLE_RATES": {},
    }
)
class GiftCardRedeemEndpointTests(APITestCase):
    url = "/api/wallet/giftcard/redeem/"

    def setUp(self):
        self.user = User.objects.create_user(username="apiuser", email="api@example.com", password="pw12345678")

    def test_requires_authentication(self):
        response = self.client.post(self.url, {"code": "anything"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_successful_redeem_returns_new_balance(self):
        card, plain = _make_card(amount="75")
        self.client.force_authenticate(user=self.user)

        response = self.client.post(self.url, {"code": plain}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["amount"], 75)
        self.assertEqual(response.data["balance"], 75)

    def test_invalid_code_returns_404(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, {"code": "not-a-real-code"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_already_redeemed_returns_409(self):
        card, plain = _make_card(amount="10")
        self.client.force_authenticate(user=self.user)
        self.client.post(self.url, {"code": plain}, format="json")

        response = self.client.post(self.url, {"code": plain}, format="json")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_blank_code_returns_400(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, {"code": ""}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
