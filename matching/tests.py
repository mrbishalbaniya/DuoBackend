from django.contrib.auth import get_user_model
from django.test import TestCase

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
        self.viewer_profile.pref_verified_only = False
        self.viewer_profile.save(update_fields=["pref_verified_only"])
        self._create_candidate("verified_match", age=26, gender="F", is_verified=True)
        self._create_candidate("backup", age=27, gender="F", relationship_goal="casual")

        result = discover_profiles(self.viewer)
        usernames = [profile.user.username for profile in result.profiles]
        self.assertIn("verified_match", usernames)
        self.assertIn("backup", usernames)
        self.assertTrue(result.expanded_search)

    def test_recycled_skips_when_fresh_pool_exhausted(self):
        first = self._create_candidate("first", age=26, gender="F", is_verified=True)
        second = self._create_candidate("second", age=27, gender="F", is_verified=True)
        Swipe.objects.create(from_user=self.viewer, to_user=first.user, action="SKIP")
        Swipe.objects.create(from_user=self.viewer, to_user=second.user, action="SKIP")

        result = discover_profiles(self.viewer)
        usernames = [profile.user.username for profile in result.profiles]
        self.assertGreater(len(usernames), 0)
        self.assertTrue(result.recycled_skips)

    def test_rank_discover_profiles_backward_compatible(self):
        self._create_candidate("one", age=26, gender="F", is_verified=True)
        profiles = rank_discover_profiles(self.viewer)
        self.assertEqual(len(profiles), 1)
