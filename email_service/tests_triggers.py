"""Each real event sends the right templated email to the right person."""

from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from email_service.constants import EmailEvent
from email_service.models import EmailTemplate

User = get_user_model()


def make_user(username, **profile_fields):
    user = User.objects.create_user(username=username, email=f"{username}@example.com", password="x-Pass-12345")
    profile = Profile.objects.filter(user=user).first() or Profile.objects.create(user=user)
    if profile_fields:
        Profile.objects.filter(pk=profile.pk).update(**profile_fields)
    user.refresh_from_db()
    return user


class TriggerTests(TestCase):
    def setUp(self):
        patcher = mock.patch("email_service.service.send_email")
        self.send = patcher.start()
        self.addCleanup(patcher.stop)

    def sent(self):
        """[(event, to, context)] for every email sent so far."""
        return [(c.kwargs["event"], c.kwargs["to"], c.kwargs.get("context", {})) for c in self.send.call_args_list]

    def events_to(self, email):
        return [event for event, to, _ in self.sent() if to == email]

    def test_welcome_on_onboarding_complete(self):
        user = make_user("amy", full_name="Amy Rai")
        with self.captureOnCommitCallbacks(execute=True):
            profile = user.profile
            profile.is_onboarded = True
            profile.save()
        self.assertEqual(self.events_to("amy@example.com"), [EmailEvent.WELCOME])
        self.assertEqual(self.sent()[0][2]["user_name"], "Amy")

    def test_match_emails_both_people(self):
        from matching.models import Match

        a = make_user("ana", full_name="Ana K")
        b = make_user("bob", full_name="Bob S")
        with self.captureOnCommitCallbacks(execute=True):
            Match.objects.create(user1=a, user2=b)
        self.assertEqual(self.events_to("ana@example.com"), [EmailEvent.MATCH_NOTIFICATION])
        self.assertEqual(self.events_to("bob@example.com"), [EmailEvent.MATCH_NOTIFICATION])
        contexts = {to: ctx for _, to, ctx in self.sent()}
        self.assertEqual(contexts["ana@example.com"]["match_name"], "Bob")
        self.assertEqual(contexts["bob@example.com"]["match_name"], "Ana")

    def test_account_deactivated_and_reactivated(self):
        user = make_user("cat")
        with self.captureOnCommitCallbacks(execute=True):
            user.is_active = False
            user.save()
        with self.captureOnCommitCallbacks(execute=True):
            user.is_active = True
            user.save()
        titles = [ctx["title"] for event, _, ctx in self.sent() if event == EmailEvent.ACCOUNT_STATUS]
        self.assertEqual(titles, ["Your account has been deactivated", "Your account is active again"])

    def test_coin_topup_and_gift_card_receipts(self):
        from subscriptions.models import WalletTransaction
        from subscriptions.wallet_services import credit_wallet

        user = make_user("dan")
        with self.captureOnCommitCallbacks(execute=True):
            credit_wallet(user, Decimal("500"), total_amount=Decimal("500"), reference_id="T-1")
        with self.captureOnCommitCallbacks(execute=True):
            credit_wallet(
                user,
                Decimal("100"),
                tx_type=WalletTransaction.TYPE_GIFT_REDEEM,
                payment_method=WalletTransaction.PAYMENT_METHOD_GIFT,
            )
        titles = [ctx["title"] for event, _, ctx in self.sent() if event == EmailEvent.GENERIC]
        self.assertEqual(titles, ["Coins added to your wallet", "Gift card redeemed"])
        receipt = self.sent()[0][2]
        values = {row["label"]: row["value"] for row in receipt["details"]}
        self.assertEqual(values["Coins added"], "500 coins")
        self.assertEqual(values["Paid"], "NPR 500")
        self.assertTrue(receipt["cta_url"].endswith("/wallet"))

    def test_subscription_confirmed_and_failed(self):
        from subscriptions.models import SubscriptionPayment

        user = make_user("eve")
        payment = SubscriptionPayment.objects.create(
            user=user, transaction_uuid="U-1", amount=Decimal("499"), total_amount=Decimal("499")
        )
        with self.captureOnCommitCallbacks(execute=True):
            payment.status = SubscriptionPayment.STATUS_COMPLETE
            payment.save()
        failed = SubscriptionPayment.objects.create(
            user=user, transaction_uuid="U-2", amount=Decimal("499"), total_amount=Decimal("499")
        )
        with self.captureOnCommitCallbacks(execute=True):
            failed.status = SubscriptionPayment.STATUS_FAILED
            failed.save()
        self.assertEqual(
            self.events_to("eve@example.com"),
            [EmailEvent.SUBSCRIPTION_CONFIRMED, EmailEvent.SUBSCRIPTION_FAILED],
        )

    def test_no_email_without_address_or_for_inactive(self):
        user = make_user("fay")
        User.objects.filter(pk=user.pk).update(email="")
        user.refresh_from_db()
        with self.captureOnCommitCallbacks(execute=True):
            profile = user.profile
            profile.is_onboarded = True
            profile.save()
        self.assertEqual(self.sent(), [])


class AdminPreviewTests(TestCase):
    def setUp(self):
        from email_service.defaults import ensure_default_templates

        ensure_default_templates()
        self.admin = User.objects.create_superuser("root", "root@example.com", "x-Pass-12345")
        self.client.force_login(self.admin)

    def test_every_template_previews_cleanly(self):
        for template in EmailTemplate.objects.all():
            change = self.client.get(reverse("admin:email_service_emailtemplate_change", args=[template.pk]))
            self.assertEqual(change.status_code, 200, template.event)
            full = self.client.get(reverse("admin:email_service_emailtemplate_full_preview", args=[template.pk]))
            self.assertEqual(full.status_code, 200, template.event)
            body = full.content.decode()
            self.assertNotIn("{{", body, template.event)
            self.assertNotIn("{%", body, template.event)

    def test_announcement_page_and_send(self):
        make_user("gus", is_onboarded=True)
        url = reverse("admin:email_service_announce")
        self.assertEqual(self.client.get(url).status_code, 200)
        with mock.patch("email_service.admin.send_user_email") as send:
            response = self.client.post(
                url, {"audience": "onboarded", "title": "Hello", "message": "News", "send_all": "1"}
            )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(send.call_count, 1)
        self.assertEqual(send.call_args.args[1], EmailEvent.ADMIN_ANNOUNCEMENT)


class EmailPreferenceTests(TestCase):
    def setUp(self):
        patcher = mock.patch("email_service.service.send_email")
        self.send = patcher.start()
        self.addCleanup(patcher.stop)

    def events_to(self, email):
        return [c.kwargs["event"] for c in self.send.call_args_list if c.kwargs["to"] == email]

    def _prefs(self, user, **fields):
        from notifications.services.preferences import get_preferences

        prefs = get_preferences(user)
        for key, value in fields.items():
            setattr(prefs, key, value)
        prefs.save()

    def test_match_email_skipped_when_opted_out(self):
        from matching.models import Match

        a = make_user("cara")
        b = make_user("dev")
        self._prefs(a, email_matches=False)
        with self.captureOnCommitCallbacks(execute=True):
            Match.objects.create(user1=a, user2=b)
        self.assertEqual(self.events_to("cara@example.com"), [])
        self.assertEqual(self.events_to("dev@example.com"), [EmailEvent.MATCH_NOTIFICATION])

    def test_master_switch_blocks_optional_emails(self):
        from email_service.triggers import send_user_email

        user = make_user("eli")
        self._prefs(user, email_enabled=False)
        with self.captureOnCommitCallbacks(execute=True):
            send_user_email(user, EmailEvent.ADMIN_ANNOUNCEMENT, {"title": "Hi"})
            send_user_email(user, EmailEvent.WELCOME)
        self.assertEqual(self.events_to("eli@example.com"), [EmailEvent.WELCOME])

    def test_account_status_is_essential(self):
        user = make_user("fay")
        self._prefs(user, email_enabled=False, email_verification=False)
        with self.captureOnCommitCallbacks(execute=True):
            user.is_active = False
            user.save()
        self.assertEqual(self.events_to("fay@example.com"), [EmailEvent.ACCOUNT_STATUS])

    def test_preferences_api_updates_email_fields(self):
        from rest_framework.test import APIClient

        user = make_user("gus")
        client = APIClient()
        client.force_authenticate(user)
        res = client.patch("/api/notifications/preferences/", {"email_payments": False}, format="json")
        self.assertEqual(res.status_code, 200, res.content)
        self.assertFalse(res.json()["email_payments"])
        self.assertTrue(res.json()["email_enabled"])
