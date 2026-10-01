from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class HealthCheckTests(TestCase):
    def test_health_endpoint_returns_ok(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")


@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": (
            "accounts.authentication.CookieJWTAuthentication",
        ),
        "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
        "DEFAULT_THROTTLE_CLASSES": [],
        "DEFAULT_THROTTLE_RATES": {},
    }
)
class AuthFlowTests(APITestCase):
    def test_register_and_me(self):
        payload = {
            "email": "prodtest@example.com",
            "password": "securepass123",
            "full_name": "Prod Test",
        }
        from accounts.email_otp import mark_email_verified

        mark_email_verified(payload["email"])
        register_response = self.client.post("/api/auth/register/", payload, format="json")
        self.assertEqual(register_response.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", register_response.json()["tokens"])

        access = register_response.json()["tokens"]["access"]
        me_response = self.client.get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(me_response.status_code, status.HTTP_200_OK)
        self.assertEqual(me_response.json()["email"], "prodtest@example.com")

    @override_settings(REQUIRE_EMAIL_OTP_FOR_REGISTRATION=True)
    def test_register_requires_verified_email(self):
        payload = {
            "email": "unverified@example.com",
            "password": "securepass123",
            "full_name": "No Code",
        }
        response = self.client.post("/api/auth/register/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.json())

    @override_settings(REQUIRE_EMAIL_OTP_FOR_REGISTRATION=True)
    def test_register_with_verified_code(self):
        from unittest.mock import patch

        from accounts.email_otp import _cache_key

        email = "coded@example.com"
        with patch("accounts.email_otp.send_email"):
            send = self.client.post("/api/auth/email/send-otp/", {"email": email}, format="json")
        self.assertEqual(send.status_code, status.HTTP_200_OK)

        from django.core.cache import cache

        code = cache.get(_cache_key(email))
        verify = self.client.post(
            "/api/auth/email/verify-otp/", {"email": email, "otp": code}, format="json"
        )
        self.assertEqual(verify.status_code, status.HTTP_200_OK)

        response = self.client.post(
            "/api/auth/register/",
            {"email": email, "password": "securepass123", "full_name": "Coded"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_send_otp_rejects_existing_email(self):
        from django.contrib.auth import get_user_model

        get_user_model().objects.create_user(
            username="taken@example.com", email="taken@example.com", password="securepass123"
        )
        response = self.client.post(
            "/api/auth/email/send-otp/", {"email": "taken@example.com"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["code"], "email_taken")

    def test_login_rejects_invalid_credentials(self):
        response = self.client.post(
            "/api/auth/login/",
            {"username": "missing@example.com", "password": "wrongpassword"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_accepts_email_for_custom_username_account(self):
        from django.contrib.auth import get_user_model

        get_user_model().objects.create_user(
            username="coolname", email="person@example.com", password="StrongPass!234"
        )
        for identifier in ("person@example.com", "Person@Example.com", "CoolName"):
            response = self.client.post(
                "/api/auth/login/",
                {"username": identifier, "password": "StrongPass!234"},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK, identifier)

    def test_google_only_account_can_set_password_via_reset(self):
        from unittest.mock import patch

        from django.contrib.auth import get_user_model
        from django.core.cache import cache

        cache.clear()
        user = get_user_model().objects.create(username="g@example.com", email="g@example.com")
        user.set_unusable_password()
        user.save()

        with patch("accounts.password_reset.send_email") as send:
            forgot = self.client.post(
                "/api/auth/password/forgot/", {"email": "g@example.com"}, format="json"
            )
        self.assertEqual(forgot.status_code, status.HTTP_200_OK)
        send.assert_called_once()
        code = send.call_args.kwargs["context"]["otp_code"]

        reset = self.client.post(
            "/api/auth/password/reset/",
            {"email": "g@example.com", "otp": code, "password": "Newpass!2345"},
            format="json",
        )
        self.assertEqual(reset.status_code, status.HTTP_200_OK, reset.content)
        user.refresh_from_db()
        self.assertTrue(user.check_password("Newpass!2345"))


@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": (
            "accounts.authentication.CookieJWTAuthentication",
        ),
        "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
        "DEFAULT_THROTTLE_CLASSES": [],
        "DEFAULT_THROTTLE_RATES": {},
    }
)
class ProfilePhotoApprovalGateTests(APITestCase):
    """Do NOT trust frontend validation — these hit ProfileSerializer.validate
    directly via the real PUT endpoint, the single enforcement point that
    keeps every discovery/matching/chat surface safe."""

    def setUp(self):
        from django.contrib.auth import get_user_model

        from accounts.models import Profile

        User = get_user_model()
        self.user = User.objects.create_user(
            username="phototest", email="phototest@example.com", password="pw12345678"
        )
        Profile.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)

    def _put(self, payload):
        return self.client.put("/api/profiles/me/", payload, format="json")

    def test_cannot_set_a_photo_url_with_no_backing_approved_record(self):
        response = self._put({"photo_url": "https://evil.example.com/unapproved.jpg", "photo_urls": []})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("photo_urls", response.json())

    def test_can_set_a_photo_url_backed_by_an_approved_profilephoto(self):
        from photo_verification.constants import ModerationStatus
        from photo_verification.models import ProfilePhoto

        ProfilePhoto.objects.create(
            user=self.user,
            url="https://example.com/ok.jpg",
            status=ModerationStatus.APPROVED,
            order=0,
        )
        response = self._put({"photo_url": "https://example.com/ok.jpg", "photo_urls": []})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_manual_review_photo_can_be_set(self):
        """Registration/profile save must not block on a human reviewer — a
        MANUAL_REVIEW photo (borderline content-safety/quality, e.g. multiple
        faces) is usable immediately, same as APPROVED. Only REJECTED is
        blocked. See accounts/serializers.py ProfileSerializer.validate."""
        from photo_verification.constants import ModerationStatus
        from photo_verification.models import ProfilePhoto

        ProfilePhoto.objects.create(
            user=self.user,
            url="https://example.com/borderline.jpg",
            status=ModerationStatus.MANUAL_REVIEW,
            order=0,
        )
        response = self._put({"photo_url": "https://example.com/borderline.jpg", "photo_urls": []})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_rejected_photo_cannot_be_set(self):
        from photo_verification.constants import ModerationStatus
        from photo_verification.models import ProfilePhoto

        ProfilePhoto.objects.create(
            user=self.user,
            url="https://example.com/bad.jpg",
            status=ModerationStatus.REJECTED,
            order=0,
        )
        response = self._put({"photo_url": "https://example.com/bad.jpg", "photo_urls": []})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_another_users_approved_photo_cannot_be_used(self):
        """A URL approved for one user must not let a different user claim it."""
        from django.contrib.auth import get_user_model

        from photo_verification.constants import ModerationStatus
        from photo_verification.models import ProfilePhoto

        User = get_user_model()
        other = User.objects.create_user(username="otherphoto", email="otherphoto@example.com", password="pw12345678")
        ProfilePhoto.objects.create(
            user=other, url="https://example.com/theirs.jpg", status=ModerationStatus.APPROVED, order=0
        )
        response = self._put({"photo_url": "https://example.com/theirs.jpg", "photo_urls": []})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_existing_urls_are_grandfathered_on_unrelated_edit(self):
        """Editing bio shouldn't be blocked just because photo fields aren't
        in the request at all, or because previously-saved URLs (from before
        this gate existed) aren't individually re-validated on every save."""
        self.user.profile.photo_url = "https://example.com/legacy.jpg"
        self.user.profile.save(update_fields=["photo_url"])

        response = self.client.put("/api/profiles/me/", {"bio": "hello world"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": (
            "accounts.authentication.CookieJWTAuthentication",
        ),
        "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
        "DEFAULT_THROTTLE_CLASSES": [],
        "DEFAULT_THROTTLE_RATES": {},
    }
)
class ProfileAgeGateTests(APITestCase):
    """Server-side 18+ enforcement — previously frontend-only."""

    def setUp(self):
        from django.contrib.auth import get_user_model

        from accounts.models import Profile

        User = get_user_model()
        self.user = User.objects.create_user(
            username="agetest", email="agetest@example.com", password="pw12345678"
        )
        Profile.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)

    def test_under_18_rejected(self):
        response = self.client.put("/api/profiles/me/", {"age": 16}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("age", response.json())

    def test_18_and_over_accepted(self):
        response = self.client.put("/api/profiles/me/", {"age": 18}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class UsernameTests(APITestCase):
    def test_generate_username_uses_name(self):
        from accounts.usernames import generate_username

        name = generate_username("Bishal Baniya", "x@example.com")
        self.assertRegex(name, r"^bishal\.baniya\d{4}$")

    def test_user_can_change_username(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(username="first.name1234", email="a@example.com", password="StrongPass!234")
        User.objects.create_user(username="taken.name", email="b@example.com", password="StrongPass!234")
        self.client.force_authenticate(user)

        ok = self.client.patch("/api/auth/me/username/", {"username": "@New.Name_1"}, format="json")
        self.assertEqual(ok.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.username, "new.name_1")

        for bad in ("Taken.Name", "ab", "bad name", ".dot"):
            resp = self.client.patch("/api/auth/me/username/", {"username": bad}, format="json")
            self.assertEqual(resp.status_code, 400, bad)


class DuplicateEmailLoginTests(APITestCase):
    def test_login_prefers_onboarded_duplicate(self):
        from django.contrib.auth import get_user_model

        from accounts.models import Profile

        User = get_user_model()
        half = User.objects.create_user(username="half.done1111", email="dup@example.com", password="StrongPass!234")
        full = User.objects.create_user(username="full.done2222", email="dup@example.com", password="StrongPass!234")
        Profile.objects.get_or_create(user=half)
        profile, _ = Profile.objects.get_or_create(user=full)
        profile.is_onboarded = True
        profile.save()

        resp = self.client.post(
            "/api/auth/login/",
            {"username": "dup@example.com", "password": "StrongPass!234"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["user"]["username"], "full.done2222")


class PublicProfilePrivacyTests(APITestCase):
    def test_other_users_do_not_see_private_details(self):
        import json

        from django.contrib.auth import get_user_model
        from django.test import RequestFactory

        from accounts.models import Profile
        from accounts.serializers import ProfileSerializer

        User = get_user_model()
        owner = User.objects.create_user(username="owner.p1", email="o@example.com", password="StrongPass!234")
        viewer = User.objects.create_user(username="viewer.p1", email="v@example.com", password="StrongPass!234")
        profile, _ = Profile.objects.get_or_create(user=owner)
        profile.pref_values = json.dumps({
            "height": "168 cm", "caste": "Brahmin", "languages": ["Nepali"],
            "dateOfBirth": "2000-01-01", "birthTime": "05:30", "gotra": "Kashyap",
            "monthlyIncome": "50k_100k", "preferredCaste": "Chhetri",
        })
        profile.save()

        request = RequestFactory().get("/")
        request.user = viewer
        data = ProfileSerializer(profile, context={"request": request}).data
        public = json.loads(data["pref_values"])
        self.assertEqual(public, {"height": "168 cm", "caste": "Brahmin", "languages": ["Nepali"]})
        self.assertNotIn("profile_checklist", data)

        request.user = owner
        own = json.loads(ProfileSerializer(profile, context={"request": request}).data["pref_values"])
        self.assertEqual(own["birthTime"], "05:30")


class OwnAccountDataTests(APITestCase):
    def test_me_returns_own_phone_after_update(self):
        from django.contrib.auth import get_user_model

        from accounts.models import Profile

        user = get_user_model().objects.create_user(username="phone.owner", email="po@example.com", password="StrongPass!234")
        Profile.objects.get_or_create(user=user)
        self.client.force_authenticate(user)
        saved = self.client.put(
            "/api/profiles/me/", {"phone_country_code": "+977", "phone_number": "9812345678"}, format="json"
        )
        self.assertEqual(saved.status_code, 200)
        profile = self.client.get("/api/auth/me/").json()["profile"]
        self.assertEqual(profile["phone_number"], "9812345678")
        self.assertEqual(profile["phone_country_code"], "+977")
