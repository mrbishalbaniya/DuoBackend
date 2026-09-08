from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from photo_verification.constants import ModerationStatus
from photo_verification.models import ProfilePhoto
from photo_verification.views import PhotoUploadView

User = get_user_model()


@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_AUTHENTICATION_CLASSES": ("accounts.authentication.CookieJWTAuthentication",),
        "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
        "DEFAULT_THROTTLE_CLASSES": [],
        "DEFAULT_THROTTLE_RATES": {},
    }
)
class ProfilePhotoEndpointTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner", email="owner@example.com", password="pw12345678")
        self.other = User.objects.create_user(username="other", email="other@example.com", password="pw12345678")

        self.approved = ProfilePhoto.objects.create(
            user=self.owner, url="https://example.com/a.jpg", status=ModerationStatus.APPROVED, order=0
        )
        self.pending = ProfilePhoto.objects.create(
            user=self.owner, url="https://example.com/b.jpg", status=ModerationStatus.MANUAL_REVIEW, order=1
        )
        self.others_photo = ProfilePhoto.objects.create(
            user=self.other, url="https://example.com/c.jpg", status=ModerationStatus.APPROVED, order=0
        )

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    # --- Auth required ---

    def test_mine_requires_auth(self):
        response = self.client.get("/api/photos/mine/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_requires_auth(self):
        response = self.client.delete(f"/api/photos/{self.approved.id}/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- Scoping / IDOR ---

    def test_mine_only_returns_own_photos(self):
        self._auth(self.owner)
        response = self.client.get("/api/photos/mine/")
        ids = {p["id"] for p in response.json()}
        self.assertEqual(ids, {self.approved.id, self.pending.id})
        self.assertNotIn(self.others_photo.id, ids)

    def test_cannot_delete_another_users_photo(self):
        self._auth(self.owner)
        response = self.client.delete(f"/api/photos/{self.others_photo.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(ProfilePhoto.objects.filter(id=self.others_photo.id).exists())

    def test_cannot_set_primary_on_another_users_photo(self):
        self._auth(self.owner)
        response = self.client.post(f"/api/photos/{self.others_photo.id}/set-primary/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_reorder_another_users_photo(self):
        self._auth(self.owner)
        response = self.client.patch(
            "/api/photos/reorder/", {"photo_ids": [self.others_photo.id]}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --- Approval gate ---

    def test_set_primary_rejects_unapproved_photo(self):
        self._auth(self.owner)
        response = self.client.post(f"/api/photos/{self.pending.id}/set-primary/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_set_primary_accepts_approved_photo(self):
        self._auth(self.owner)
        response = self.client.post(f"/api/photos/{self.approved.id}/set-primary/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.approved.refresh_from_db()
        self.assertTrue(self.approved.is_primary)

    # --- Reorder ---

    def test_reorder_updates_order(self):
        self._auth(self.owner)
        response = self.client.patch(
            "/api/photos/reorder/",
            {"photo_ids": [self.pending.id, self.approved.id]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending.refresh_from_db()
        self.approved.refresh_from_db()
        self.assertEqual(self.pending.order, 0)
        self.assertEqual(self.approved.order, 1)

    # --- Delete cleans up and rebalances primary ---

    def test_delete_primary_promotes_no_replacement_when_none_approved(self):
        self._auth(self.owner)
        self.approved.is_primary = True
        self.approved.save(update_fields=["is_primary"])

        response = self.client.delete(f"/api/photos/{self.approved.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ProfilePhoto.objects.filter(id=self.approved.id).exists())
        # The only remaining photo is MANUAL_REVIEW, not APPROVED — no promotion possible.
        self.assertFalse(ProfilePhoto.objects.filter(user=self.owner, is_primary=True).exists())


class PhotoUploadThrottleConfigTests(APITestCase):
    def test_upload_view_has_a_throttle_configured(self):
        """PhotoUploadView previously had no throttle_classes at all."""
        self.assertTrue(len(PhotoUploadView.throttle_classes) > 0)
