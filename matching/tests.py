from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from accounts.models import Profile
from matching.discovery import rank_discover_profiles
from matching.models import Swipe
from matching.recommendation import discover_profiles
from matching.recommendation.scoring import compute_recommendation_score
from matching.recommendation.types import SearchConfig

User = get_user_model()


class DiscoverRecommendationTests(TestCase):
    def setUp(self):
        self.viewer = User.objects.create_user(username="viewer", password="pass12345")
        self.viewer_profile, _ = Profile.objects.get_or_create(user=self.viewer)
        self.viewer_profile.full_name = "Viewer"
        self.viewer_profile.age = 28
        self.viewer_profile.gender = "M"
        self.viewer_profile.location = "Kathmandu, Nepal"
        self.viewer_profile.is_onboarded = True
        self.viewer_profile.pref_gender = "women"
        self.viewer_profile.pref_age_min = 24
        self.viewer_profile.pref_age_max = 30
        self.viewer_profile.pref_location = "Kathmandu"
        self.viewer_profile.pref_max_distance_km = 100
        self.viewer_profile.pref_relationship_goal = "serious"
        self.viewer_profile.pref_verified_only = True
        self.viewer_profile.save()

    def _create_candidate(
        self,
        username: str,
        *,
        age: int,
        gender: str,
        location: str = "Kathmandu, Nepal",
        relationship_goal: str = "serious",
        is_verified: bool = False,
    ) -> Profile:
        user = User.objects.create_user(username=username, password="pass12345")
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.full_name = username.title()
        profile.age = age
        profile.gender = gender
        profile.location = location
        profile.relationship_goal = relationship_goal
        profile.is_verified = is_verified
        profile.is_onboarded = True
        profile.save()
        return profile

    def test_never_empty_when_other_users_exist(self):
        self._create_candidate("verified_match", age=26, gender="F", is_verified=True)
        self._create_candidate("unverified_nearby", age=27, gender="F", is_verified=False)

        result = discover_profiles(self.viewer)
        self.assertGreater(len(result.profiles), 0)

    def test_strict_match_ranks_before_relaxed_match(self):
        perfect = self._create_candidate("perfect", age=26, gender="F", is_verified=True)
        self._create_candidate("far", age=26, gender="F", location="Pokhara, Nepal", is_verified=True)

        result = discover_profiles(self.viewer)
        self.assertEqual(result.profiles[0].user.username, "perfect")
        self.assertEqual(result.profiles[0].id, perfect.id)

    def test_soft_preferences_do_not_exclude_profiles(self):
        self.viewer_profile.pref_values = '{"preferredReligion":"Hindu"}'
        self.viewer_profile.save()
        self._create_candidate("other_religion", age=26, gender="F", is_verified=True)
        other = Profile.objects.get(user__username="other_religion")
        other.religion = "Buddhist"
        other.save(update_fields=["religion"])

        result = discover_profiles(self.viewer)
        usernames = [profile.user.username for profile in result.profiles]
        self.assertIn("other_religion", usernames)

    def test_soft_preference_increases_score(self):
        self.viewer_profile.pref_values = '{"preferredReligion":"Hindu"}'
        self.viewer_profile.save()
        hindu = self._create_candidate("hindu", age=26, gender="F", is_verified=True)
        hindu.religion = "Hindu"
        hindu.save(update_fields=["religion"])
        other = self._create_candidate("other", age=26, gender="F", is_verified=True)
        other.religion = "Buddhist"
        other.save(update_fields=["religion"])

        config = SearchConfig(
            age_min=24,
            age_max=30,
            max_distance_km=100,
            location_pref="Kathmandu",
            gender="women",
            relationship_goal="serious",
            verified_only=False,
        )
        hindu_score = compute_recommendation_score(
            self.viewer_profile,
            hindu,
            distance_km=5,
            config=config,
        )
        other_score = compute_recommendation_score(
            self.viewer_profile,
            other,
            distance_km=5,
            config=config,
        )
        self.assertGreater(hindu_score, other_score)

    def test_expands_search_when_strict_pool_is_small(self):
        self._create_candidate("verified_match", age=26, gender="F", is_verified=True)
        self._create_candidate("slightly_older", age=32, gender="F", is_verified=True)

        result = discover_profiles(self.viewer)
        usernames = [profile.user.username for profile in result.profiles]
        self.assertIn("verified_match", usernames)
        self.assertIn("slightly_older", usernames)
        self.assertTrue(result.expanded_search)
        self.assertIn("age", result.meta["expansions"])

    def test_age_range_is_strict_when_expansion_disabled(self):
        self.viewer_profile.pref_expand_age = False
        self.viewer_profile.save(update_fields=["pref_expand_age"])
        self._create_candidate("in_range", age=26, gender="F", is_verified=True)
        self._create_candidate("slightly_older", age=32, gender="F", is_verified=True)

        usernames = [p.user.username for p in discover_profiles(self.viewer).profiles]
        self.assertEqual(usernames, ["in_range"])

    def test_distance_is_strict_when_expansion_disabled(self):
        self.viewer_profile.pref_expand_distance = False
        self.viewer_profile.save(update_fields=["pref_expand_distance"])
        self._create_candidate("nearby", age=26, gender="F", is_verified=True)
        self._create_candidate("pokhara", age=26, gender="F", location="Pokhara, Nepal", is_verified=True)

        usernames = [p.user.username for p in discover_profiles(self.viewer).profiles]
        self.assertEqual(usernames, ["nearby"])

    def test_distance_expands_when_allowed(self):
        self._create_candidate("pokhara", age=26, gender="F", location="Pokhara, Nepal", is_verified=True)

        result = discover_profiles(self.viewer)
        self.assertEqual([p.user.username for p in result.profiles], ["pokhara"])
        self.assertIn("distance", result.meta["expansions"])

    def test_explicit_filters_are_never_relaxed(self):
        self._create_candidate("man", age=26, gender="M", is_verified=True)
        self._create_candidate("unverified", age=26, gender="F", is_verified=False)
        self._create_candidate("casual", age=26, gender="F", relationship_goal="casual", is_verified=True)

        result = discover_profiles(self.viewer)
        self.assertEqual(result.profiles, [])

    def test_unset_goal_ranks_after_matching_goal(self):
        self._create_candidate("no_goal", age=26, gender="F", relationship_goal="", is_verified=True)
        self._create_candidate("serious", age=26, gender="F", relationship_goal="serious", is_verified=True)

        usernames = [p.user.username for p in discover_profiles(self.viewer).profiles]
        self.assertEqual(usernames, ["serious", "no_goal"])

    def test_search_city_moves_the_distance_anchor(self):
        self.viewer_profile.pref_location = "Pokhara"
        self.viewer_profile.pref_expand_distance = False
        self.viewer_profile.save(update_fields=["pref_location", "pref_expand_distance"])
        self._create_candidate("kathmandu", age=26, gender="F", is_verified=True)
        self._create_candidate("pokhara", age=26, gender="F", location="Pokhara, Nepal", is_verified=True)

        usernames = [p.user.username for p in discover_profiles(self.viewer).profiles]
        self.assertEqual(usernames, ["pokhara"])

    def test_discover_api_returns_rounded_distance(self):
        from rest_framework.test import APIClient

        self._create_candidate("pokhara", age=26, gender="F", location="Pokhara, Nepal", is_verified=True)
        ghost = self._create_candidate("ghost", age=26, gender="F", is_verified=True)
        ghost.location_ghost_mode = True
        ghost.save(update_fields=["location_ghost_mode"])

        client = APIClient()
        client.force_authenticate(self.viewer)
        response = client.get("/api/profiles/discover/")
        self.assertEqual(response.status_code, 200)
        by_name = {row["username"]: row for row in response.json()}

        self.assertIsNone(by_name["ghost"]["distance_km"])
        self.assertEqual(by_name["ghost"]["location"], "")
        # Kathmandu to Pokhara is roughly 140 km; above 100 km it's rounded to tens.
        self.assertEqual(by_name["pokhara"]["distance_km"] % 10, 0)
        self.assertTrue(120 <= by_name["pokhara"]["distance_km"] <= 160)

    def test_recycled_skips_when_fresh_pool_exhausted(self):
        first = self._create_candidate("first", age=26, gender="F", is_verified=True)
        second = self._create_candidate("second", age=27, gender="F", is_verified=True)
        Swipe.objects.create(from_user=self.viewer, to_user=first.user, action="SKIP")
        Swipe.objects.create(from_user=self.viewer, to_user=second.user, action="SKIP")

        result = discover_profiles(self.viewer)
        usernames = [profile.user.username for profile in result.profiles]
        self.assertGreater(len(usernames), 0)
        self.assertTrue(result.recycled_skips)
        self.assertIn("first", usernames)
        self.assertIn("second", usernames)

    def test_liked_profiles_are_not_recycled(self):
        liked = self._create_candidate("liked", age=26, gender="F", is_verified=True)
        skipped = self._create_candidate("skipped", age=27, gender="F", is_verified=True)
        Swipe.objects.create(from_user=self.viewer, to_user=liked.user, action="LIKE")
        Swipe.objects.create(from_user=self.viewer, to_user=skipped.user, action="SKIP")

        result = discover_profiles(self.viewer)
        usernames = [profile.user.username for profile in result.profiles]
        self.assertNotIn("liked", usernames)
        self.assertIn("skipped", usernames)
        self.assertTrue(result.recycled_skips)

    def test_rank_discover_profiles_backward_compatible(self):
        self._create_candidate("one", age=26, gender="F", is_verified=True)
        profiles = rank_discover_profiles(self.viewer)
        self.assertEqual(len(profiles), 1)


class RewindTests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient

        self.user = User.objects.create_user(username="rewinder", password="pass12345")
        profile, _ = Profile.objects.get_or_create(user=self.user)
        profile.is_onboarded = True
        profile.location = "Kathmandu, Nepal"
        profile.save()
        self.other = User.objects.create_user(username="other", password="pass12345")
        other_profile, _ = Profile.objects.get_or_create(user=self.other)
        other_profile.full_name = "Other"
        other_profile.is_onboarded = True
        other_profile.location = "Kathmandu, Nepal"
        other_profile.save()
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _grant(self, feature="rewind"):
        from datetime import timedelta

        from django.utils import timezone

        from subscriptions.models import SubscriptionPayment

        SubscriptionPayment.objects.create(
            user=self.user,
            plan_id="rewind_30d",
            feature=feature,
            transaction_uuid=f"T-{feature}",
            amount=1,
            total_amount=1,
            status="complete",
            expires_at=timezone.now() + timedelta(days=5),
        )

    def test_requires_rewind_pass(self):
        Swipe.objects.create(from_user=self.user, to_user=self.other, action="SKIP")
        response = self.client.post("/api/matching/rewind/", {}, format="json")
        self.assertEqual(response.status_code, 402)
        self.assertTrue(response.json()["premium_required"])
        self.assertTrue(Swipe.objects.filter(from_user=self.user).exists())

    def test_legacy_all_pass_does_not_include_rewind(self):
        self._grant("all")
        Swipe.objects.create(from_user=self.user, to_user=self.other, action="SKIP")
        response = self.client.post("/api/matching/rewind/", {}, format="json")
        self.assertEqual(response.status_code, 402)

    def test_rewinds_latest_swipe_and_returns_profile(self):
        self._grant()
        Swipe.objects.create(from_user=self.user, to_user=self.other, action="LIKE")
        response = self.client.post("/api/matching/rewind/", {}, format="json")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["undone_action"], "LIKE")
        self.assertEqual(body["profile"]["user_id"], self.other.id)
        self.assertIsNotNone(body["profile"]["distance_km"])
        self.assertFalse(Swipe.objects.filter(from_user=self.user).exists())

    def test_nothing_to_rewind(self):
        self._grant()
        response = self.client.post("/api/matching/rewind/", {}, format="json")
        self.assertEqual(response.status_code, 404)

    def test_cannot_rewind_a_match(self):
        from matching.models import Match

        self._grant()
        Swipe.objects.create(from_user=self.user, to_user=self.other, action="LIKE")
        Match.objects.create(user1=self.user, user2=self.other)
        response = self.client.post(
            "/api/matching/rewind/", {"to_user_id": self.other.id}, format="json"
        )
        self.assertEqual(response.status_code, 409)
        self.assertTrue(Swipe.objects.filter(from_user=self.user).exists())


@override_settings(FREE_LIKES_PER_WINDOW=3, FREE_LIKES_WINDOW_HOURS=12)
class LikeQuotaTests(TestCase):
    """Free users: limited Likes per rolling window, unlimited left swipes."""

    def setUp(self):
        from django.core.cache import cache
        from rest_framework.test import APIClient

        cache.clear()
        self.user = self._make_user("liker")
        self.others = [self._make_user(f"target{i}") for i in range(6)]
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @staticmethod
    def _make_user(username):
        user = User.objects.create_user(username=username, password="pass12345")
        profile, _ = Profile.objects.get_or_create(user=user)
        profile.full_name = username.title()
        profile.is_onboarded = True
        profile.save()
        return user

    def _swipe(self, target, action="LIKE", client=None):
        return (client or self.client).post(
            "/api/matching/swipe/", {"to_user_id": target.id, "action": action}, format="json"
        )

    def _grant_unlimited(self):
        from datetime import timedelta

        from django.utils import timezone

        from subscriptions.models import SubscriptionPayment

        SubscriptionPayment.objects.create(
            user=self.user,
            plan_id="unlimited_likes_30d",
            feature="unlimited_likes",
            transaction_uuid="T-unlimited",
            amount=1,
            total_amount=1,
            status="complete",
            expires_at=timezone.now() + timedelta(days=5),
        )

    def test_counts_down_and_blocks_likes_at_limit(self):
        remaining = [self._swipe(t).json()["likes_remaining"] for t in self.others[:3]]
        self.assertEqual(remaining, [2, 1, 0])

        blocked = self._swipe(self.others[3])
        self.assertEqual(blocked.status_code, 429)
        body = blocked.json()
        self.assertEqual(body["code"], "like_limit_reached")
        self.assertEqual(body["likes_remaining"], 0)
        self.assertIsNotNone(body["reset_at"])
        self.assertFalse(Swipe.objects.filter(from_user=self.user, to_user=self.others[3]).exists())

    def test_left_swipes_are_unlimited_and_free(self):
        for target in self.others[:3]:
            self._swipe(target)
        for target in self.others[3:]:
            response = self._swipe(target, "SKIP")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["likes_remaining"], 0)

    def test_likes_expire_after_window(self):
        from datetime import timedelta

        from django.utils import timezone

        from matching.models import LikeEvent

        for target in self.others[:3]:
            self._swipe(target)
        LikeEvent.objects.filter(user=self.user).update(created_at=timezone.now() - timedelta(hours=13))
        response = self._swipe(self.others[3])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["likes_remaining"], 2)

    def test_duplicate_like_is_noop_and_not_counted(self):
        self._swipe(self.others[0])
        again = self._swipe(self.others[0])
        self.assertEqual(again.status_code, 200)
        self.assertTrue(again.json()["duplicate"])
        self.assertEqual(again.json()["likes_remaining"], 2)
        self.assertEqual(Swipe.objects.filter(from_user=self.user).count(), 1)

    def test_rewound_like_still_counts(self):
        from matching.likes import get_like_quota

        self._swipe(self.others[0])
        Swipe.objects.filter(from_user=self.user).delete()  # what rewind/unlike do
        self.assertEqual(get_like_quota(self.user).remaining, 2)

    def test_self_swipe_rejected(self):
        response = self._swipe(self.user)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "self_swipe")

    def test_mutual_like_creates_exactly_one_match(self):
        from rest_framework.test import APIClient

        from matching.models import Match

        other = self.others[0]
        other_client = APIClient()
        other_client.force_authenticate(other)

        first = self._swipe(other)
        self.assertFalse(first.json()["is_match"])
        second = self._swipe(self.user, client=other_client)
        self.assertTrue(second.json()["is_match"])
        again = self._swipe(self.user, action="SUPERLIKE", client=other_client)
        self.assertFalse(again.json()["is_match"])
        self.assertEqual(Match.objects.count(), 1)

    def test_cannot_skip_someone_you_matched_with(self):
        from matching.models import Match

        other = self.others[0]
        Swipe.objects.create(from_user=other, to_user=self.user, action="LIKE")
        self.assertTrue(self._swipe(other).json()["is_match"])
        response = self._swipe(other, "SKIP")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Match.objects.count(), 1)

    def test_skip_then_like_counts_one_like(self):
        self._swipe(self.others[0], "SKIP")
        response = self._swipe(self.others[0])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["likes_remaining"], 2)

    def test_unlimited_pass_lifts_limit(self):
        self._grant_unlimited()
        for target in self.others[:5]:
            response = self._swipe(target)
            self.assertEqual(response.status_code, 200)
            self.assertIsNone(response.json()["likes_remaining"])
            self.assertTrue(response.json()["likes"]["unlimited"])

    def test_quota_endpoint(self):
        self._swipe(self.others[0])
        data = self.client.get("/api/matching/likes/quota/").json()
        self.assertEqual(data["limit"], 3)
        self.assertEqual(data["likes_remaining"], 2)
        self.assertEqual(data["window_hours"], 12)
