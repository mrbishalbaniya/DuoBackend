"""Tests for selfie-verification hardening: random steps, identity continuity,
timing limits, and badge revocation when new photos are added."""

from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import Profile
from photo_verification.constants import LIVENESS_STEP_POOL, LIVENESS_STEPS_PER_SESSION
from photo_verification.services import liveness_session as ls


class FakeSession:
    def __init__(self, data=None):
        self.liveness_data = data or {}
        self.saved = False

    def save(self, update_fields=None):
        self.saved = True


class RandomStepsTests(TestCase):
    def test_steps_are_random_valid_and_persisted(self):
        seen = set()
        for _ in range(40):
            session = FakeSession()
            steps = ls.ensure_session_steps(session)
            self.assertEqual(len(steps), LIVENESS_STEPS_PER_SESSION)
            self.assertEqual(len(set(steps)), len(steps))
            self.assertTrue(set(steps) <= set(LIVENESS_STEP_POOL))
            self.assertTrue({"smile", "blink"} & set(steps))
            self.assertTrue({"head_left", "head_right"} & set(steps))
            # Stable once chosen.
            self.assertEqual(ls.ensure_session_steps(session), steps)
            seen.add(tuple(steps))
        self.assertGreater(len(seen), 3, "steps should vary between sessions")


class IdentityCheckTests(TestCase):
    def _data(self, *vectors):
        return {ls.FRAMES_KEY: [{"embedding": v, "detector": "insightface"} for v in vectors]}

    def test_same_person_passes(self):
        ok, score, _ = ls.identity_check(self._data([1, 0, 0], [0.95, 0.1, 0]), [1, 0.05, 0], "insightface")
        self.assertTrue(ok)
        self.assertGreater(score, 0.9)

    def test_different_person_in_any_frame_fails(self):
        ok, _, reason = ls.identity_check(self._data([1, 0, 0], [0, 1, 0]), [1, 0, 0], "insightface")
        self.assertFalse(ok)
        self.assertIn("doesn't match", reason)

    def test_missing_frames_fails(self):
        ok, _, _ = ls.identity_check({}, [1, 0, 0], "insightface")
        self.assertFalse(ok)


class TimingTests(TestCase):
    def test_liveness_duration_limit(self):
        old = (timezone.now() - timedelta(minutes=10)).isoformat()
        self.assertTrue(ls.liveness_time_exceeded({ls.STARTED_KEY: old}))
        self.assertFalse(ls.liveness_time_exceeded({ls.STARTED_KEY: timezone.now().isoformat()}))

    def test_selfie_delay_limit(self):
        self.assertTrue(ls.selfie_too_late({}))
        old = (timezone.now() - timedelta(minutes=10)).isoformat()
        self.assertTrue(ls.selfie_too_late({ls.LAST_FRAME_KEY: old}))
        self.assertFalse(ls.selfie_too_late({ls.LAST_FRAME_KEY: timezone.now().isoformat()}))

    def test_record_frame_stamps_and_fingerprints(self):
        fake = mock.Mock(embedding=[0.1, 0.2], detector="insightface")
        with mock.patch.object(ls, "extract_face_embedding", return_value=fake):
            data = ls.record_frame({}, rgb=None)
            data = ls.record_frame(data, rgb=None)
        self.assertEqual(len(data[ls.FRAMES_KEY]), 2)
        self.assertIn(ls.STARTED_KEY, data)
        self.assertIn(ls.LAST_FRAME_KEY, data)


class BadgeRevocationTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="v1", email="v1@example.com", password="x-Pass-123")
        self.profile = Profile.objects.get(user=user) if Profile.objects.filter(user=user).exists() else Profile.objects.create(user=user)
        Profile.objects.filter(pk=self.profile.pk).update(
            is_verified=True, photo_url="https://img/a.jpg", photo_urls=["https://img/b.jpg"]
        )
        self.profile.refresh_from_db()

    def test_adding_new_photo_revokes_badge(self):
        self.profile.photo_urls = ["https://img/b.jpg", "https://img/new.jpg"]
        self.profile.save()
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.is_verified)

    def test_new_photo_with_update_fields_revokes_badge(self):
        self.profile.photo_url = "https://img/new.jpg"
        self.profile.save(update_fields=["photo_url"])
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.is_verified)

    def test_reorder_or_remove_keeps_badge(self):
        self.profile.photo_url = "https://img/b.jpg"
        self.profile.photo_urls = []
        self.profile.save()
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_verified)
