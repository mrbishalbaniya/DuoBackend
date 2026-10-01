import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import Profile
from matching.compatibility import compute_compatibility, dice, interests
from matching.services import create_match_between

User = get_user_model()


def make_profile(username, **fields):
    user = User.objects.create_user(username=username, password="pass12345")
    profile, _ = Profile.objects.get_or_create(user=user)
    defaults = dict(full_name=username.title(), age=27, gender="F", location="Kathmandu, Nepal",
                    pref_age_min=22, pref_age_max=32, pref_max_distance_km=50, is_onboarded=True)
    defaults.update(fields)
    prefs = defaults.pop("prefs", None)
    for k, v in defaults.items():
        setattr(profile, k, v)
    if prefs is not None:
        profile.pref_values = json.dumps(prefs)
    profile.save()
    return profile


class DiceAndInterestTests(TestCase):
    def test_dice_coefficient(self):
        self.assertEqual(dice({"a", "b"}, {"a", "b"}), 1.0)
        self.assertEqual(dice({"a", "b"}, {"c"}), 0.0)
        self.assertAlmostEqual(dice({"a", "b", "c"}, {"a", "d"}), 2 * 1 / 5)
        self.assertIsNone(dice(set(), {"a"}))

    def test_habits_and_personality_are_not_hobbies(self):
        p = make_profile("tags", lifestyle_tags=["Travel", "smoking:no", "introvert", "Vegetarian", "Music"])
        self.assertEqual(set(interests(p)), {"travel", "music"})


class CompatibilityTests(TestCase):
    def test_scores_are_deterministic_and_bounded(self):
        a = make_profile("a1", lifestyle_tags=["Travel", "Music"], religion="Hindu")
        b = make_profile("b1", gender="M", lifestyle_tags=["Travel", "Yoga"], religion="Buddhist")
        first = compute_compatibility(a, b)
        second = compute_compatibility(a, b)
        self.assertEqual(first, second)
        for v in (first.compatibility_score, first.values_score, first.lifestyle_score,
                  first.career_score, first.hobbies_score):
            self.assertTrue(0 <= v <= 100)

    def test_similar_pair_scores_higher_than_dissimilar_pair(self):
        base = dict(religion="Hindu", relationship_goal="serious", work_preference="Private",
                    education="Bachelor in Computer Application", occupation="Software developer",
                    lifestyle_tags=["Travel", "Music", "Hiking", "smoking:no"])
        a = make_profile("a2", **base)
        similar = make_profile("b2", gender="M", **base)
        different = make_profile(
            "c2", gender="M", religion="Christian", relationship_goal="casual", work_preference="Business",
            education="SEE", occupation="Chef", lifestyle_tags=["Gaming", "Football", "smoking:yes"],
            location="Biratnagar, Nepal", age=45)
        self.assertGreater(compute_compatibility(a, similar).compatibility_score,
                           compute_compatibility(a, different).compatibility_score + 25)

    def test_shared_interests_are_the_real_overlap(self):
        a = make_profile("a3", lifestyle_tags=["Travel", "Music", "Reading"])
        b = make_profile("b3", gender="M", lifestyle_tags=["music", "Travel", "Cooking"])
        result = compute_compatibility(a, b)
        self.assertEqual(result.shared_interests, ["Music", "Travel"])
        self.assertEqual(result.hobbies_score, round(100 * 2 * 2 / 6))

    def test_missing_data_is_neutral(self):
        a = make_profile("a4", age=None, location="", lifestyle_tags=[])
        b = make_profile("b4", gender="M", age=None, location="", lifestyle_tags=[])
        result = compute_compatibility(a, b)
        self.assertEqual(
            (result.values_score, result.lifestyle_score, result.career_score, result.hobbies_score), (50, 50, 50, 50))

    def test_closed_inter_religion_lowers_values(self):
        a = make_profile("a5", religion="Hindu", prefs={"interReligion": "no"})
        same = make_profile("b5", gender="M", religion="Hindu", prefs={"interReligion": "no"})
        other = make_profile("c5", gender="M", religion="Christian", prefs={"interReligion": "no"})
        self.assertEqual(compute_compatibility(a, same).values_score, 100)
        self.assertEqual(compute_compatibility(a, other).values_score, 20)

    def test_smoking_clash_lowers_lifestyle(self):
        a = make_profile("a6", location="", age=None, lifestyle_tags=["smoking:no"])
        b = make_profile("b6", gender="M", location="", age=None, lifestyle_tags=["smoking:yes"])
        c = make_profile("c6", gender="M", location="", age=None, lifestyle_tags=["Non-Smoker"])
        self.assertEqual(compute_compatibility(a, b).lifestyle_score, 0)
        self.assertEqual(compute_compatibility(a, c).lifestyle_score, 100)

    def test_order_of_profiles_does_not_matter(self):
        a = make_profile("a7", lifestyle_tags=["Travel"], religion="Hindu", age=26)
        b = make_profile("b7", gender="M", lifestyle_tags=["Travel", "Yoga"], religion="Hindu", age=29)
        self.assertEqual(compute_compatibility(a, b).compatibility_score,
                         compute_compatibility(b, a).compatibility_score)


class MatchCreationUsesCompatibilityTests(TestCase):
    def test_match_stores_computed_scores_not_random(self):
        a = make_profile("a8", lifestyle_tags=["Travel", "Music"], religion="Hindu")
        b = make_profile("b8", gender="M", lifestyle_tags=["Travel", "Music"], religion="Hindu")
        expected = compute_compatibility(a, b)
        match, created = create_match_between(a.user, b.user, notify=False)
        self.assertTrue(created)
        self.assertEqual(match.compatibility_score, expected.compatibility_score)
        self.assertEqual(match.hobbies_score, 100)
        self.assertEqual(match.shared_interests, ["Music", "Travel"])
        self.assertIn("Both enjoy Music, Travel", match.spark_factors)

    def test_admin_override_changes_only_overall_score(self):
        a = make_profile("a9", lifestyle_tags=["Travel"])
        b = make_profile("b9", gender="M", lifestyle_tags=["Yoga"])
        expected = compute_compatibility(a, b)
        match, _ = create_match_between(a.user, b.user, compatibility_score=90, notify=False)
        self.assertEqual(match.compatibility_score, 90)
        self.assertEqual(match.hobbies_score, expected.hobbies_score)
