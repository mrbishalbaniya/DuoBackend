"""Photo upload rate limiting, error shape, and idempotent retries."""

from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from photo_verification.throttling import PhotoUploadBurstThrottle, PhotoUploadDailyThrottle

User = get_user_model()

UPLOAD_URL = "/api/photos/upload/"
TEST_RATES = {"photo_upload_burst": "1/minute", "photo_upload_daily": "100/day"}


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": ("accounts.authentication.CookieJWTAuthentication",),
        "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
        "DEFAULT_THROTTLE_CLASSES": [],
        "DEFAULT_THROTTLE_RATES": TEST_RATES,
        "EXCEPTION_HANDLER": "duo_project.exceptions.custom_exception_handler",
    },
)
class PhotoUploadLimitTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="u1", email="u1@example.com", password="pw12345678")
        self.client.force_authenticate(user=self.user)
        # THROTTLE_RATES is bound at import time, so patch it on the classes.
        for cls in (PhotoUploadBurstThrottle, PhotoUploadDailyThrottle):
            patcher = mock.patch.object(cls, "THROTTLE_RATES", TEST_RATES)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _bad_file(self):
        return SimpleUploadedFile("notes.txt", b"not an image", content_type="text/plain")

    def _image(self):
        return SimpleUploadedFile("face.jpg", b"\xff\xd8\xff" + b"0" * 100, content_type="image/jpeg")

    def test_invalid_files_do_not_use_quota(self):
        for _ in range(3):
            response = self.client.post(UPLOAD_URL, {"image": self._bad_file()}, format="multipart")
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(response.data["code"], "invalid_file")

    def test_missing_image_returns_code(self):
        response = self.client.post(UPLOAD_URL, {}, format="multipart")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "no_image")

    @mock.patch("photo_verification.views._validate_profile_image", return_value="image/jpeg")
    @mock.patch("photo_verification.views.PhotoVerificationPipeline")
    def test_rate_limit_returns_retry_after(self, pipeline_cls, _validate):
        pipeline_cls.return_value.analyze_file.side_effect = RuntimeError("model down")

        first = self.client.post(UPLOAD_URL, {"image": self._image()}, format="multipart")
        self.assertEqual(first.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertEqual(first.data["code"], "analysis_failed")

        second = self.client.post(UPLOAD_URL, {"image": self._image()}, format="multipart")
        self.assertEqual(second.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(second.data["code"], "rate_limited")
        self.assertGreater(second.data["retry_after"], 0)
        self.assertIn("Retry-After", second)
        self.assertIn("try again in", second.data["message"])

    def test_idempotent_retry_replays_stored_result(self):
        from photo_verification.views import PhotoUploadView

        key = PhotoUploadView()._idempotency_cache_key(
            mock.Mock(META={"HTTP_IDEMPOTENCY_KEY": "photo-abc"}, user=self.user)
        )
        cache.set(key, {"status": 201, "data": {"success": True, "image_url": "https://x/y.jpg"}})

        response = self.client.post(UPLOAD_URL, {}, format="multipart", HTTP_IDEMPOTENCY_KEY="photo-abc")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["image_url"], "https://x/y.jpg")
        self.assertEqual(response["Idempotent-Replayed"], "true")
