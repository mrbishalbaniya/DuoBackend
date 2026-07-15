from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Profile
from ai_profile.models import GeneratedProfileContent, SentenceTemplate
from ai_profile.services.personality_engine import PersonalityEngine
from ai_profile.services.profile_context import ProfileContext
from ai_profile.services.profile_generator import GENERATION_VERSION, ProfileGenerator
from ai_profile.services.template_engine import clear_template_cache


User = get_user_model()


class OfflineProfileGeneratorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Minimal seed for deterministic tests
        templates = [
            ("opener", "generic", "I'm {name}, based in Kathmandu.", 10, "any"),
            ("occupation", "developer", "I spend my days building software.", 10, "any"),
            ("education", "computer_science", "I enjoy solving problems.", 10, "any"),
            ("location", "generic", "I currently call {location} home.", 10, "any"),
            ("interest", "gym", "I enjoy staying active.", 10, "any"),
            ("interest", "travel", "I love exploring new places.", 10, "any"),
            ("connector", "generic", "In my free time,", 10, "any"),
            ("personality", "active", "Friends would describe me as energetic.", 10, "any"),
            ("personality", "adventurous", "I'm always open to trying something new.", 10, "any"),
            ("value", "serious", "I'm looking to build something real and lasting.", 10, "any"),
            ("closer", "generic", "Looking forward to meeting someone genuine.", 10, "any"),
            ("future", "career", "I'm focused on growing in my career.", 10, "any"),
            ("future", "family", "Family remains important to my future.", 10, "any"),
            ("future", "generic", "I want a balanced and meaningful future.", 10, "any"),
            ("looking", "goal:serious", "I'm looking for a serious relationship.", 10, "any"),
            ("looking", "age_range", "Ideally around {age_min}-{age_max}.", 10, "any"),
            ("looking", "communication", "Clear communication matters to me.", 10, "any"),
            ("looking", "generic", "I hope to meet someone kind and honest.", 10, "any"),
        ]
        SentenceTemplate.objects.bulk_create(
            [
                SentenceTemplate(
                    category=c,
                    subcategory=s,
                    text=t,
                    weight=w,
                    style=st,
                    language="en",
                    active=True,
                )
                for c, s, t, w, st in templates
            ]
        )
        clear_template_cache()

    def setUp(self):
        self.user = User.objects.create_user(
            username="ai_profile_user",
            email="ai_profile@example.com",
            password="test-pass-123",
        )
        self.profile = Profile.objects.create(
            user=self.user,
            full_name="Aarav Shrestha",
            age=28,
            gender="M",
            location="Kathmandu, Nepal",
            education="Bachelor · computer science",
            occupation="Software Developer",
            religion="Hindu",
            relationship_goal="serious",
            lifestyle_tags=["gym", "travel", "smoking:never", "exercise:often"],
            pref_age_min=24,
            pref_age_max=32,
            pref_relationship_goal="serious",
        )

    def test_personality_traits_from_interests(self):
        ctx = ProfileContext.from_profile(self.profile)
        traits = PersonalityEngine().infer(ctx)
        self.assertIn("active", traits)
        self.assertIn("adventurous", traits)

    def test_generate_bio_sections(self):
        result = ProfileGenerator(style="friendly", language="en", seed=7).generate_for_profile(
            self.profile,
            force=True,
            persist=True,
        )
        self.assertTrue(result.bio)
        self.assertTrue(result.future_goals)
        self.assertTrue(result.looking_for)
        self.assertGreaterEqual(len(result.bio.split()), 20)
        self.assertNotIn("{", result.bio)
        self.assertNotIn("{", result.looking_for)
        self.assertFalse(result.bio.endswith("and good"))
        self.assertFalse(result.cached)
        cached = GeneratedProfileContent.objects.get(user=self.user)
        self.assertEqual(cached.generation_version, GENERATION_VERSION)
        self.assertEqual(cached.generated_bio, result.bio)

    def test_empty_occupation_has_no_placeholder(self):
        self.profile.occupation = ""
        self.profile.save(update_fields=["occupation", "updated_at"])
        SentenceTemplate.objects.create(
            category="occupation",
            subcategory="generic",
            text="Professionally, I work as a {occupation} and care about doing meaningful work.",
            weight=10,
            style="any",
            language="en",
            active=True,
        )
        clear_template_cache()
        result = ProfileGenerator(style="friendly", language="en", seed=5).generate_for_profile(
            self.profile,
            force=True,
            persist=False,
        )
        self.assertNotIn("{occupation}", result.bio)
        self.assertNotIn("{", result.bio)

    def test_cache_hit_without_force(self):
        gen = ProfileGenerator(style="friendly", language="en", seed=11)
        first = gen.generate_for_profile(self.profile, force=True, persist=True)
        second = ProfileGenerator(style="friendly", language="en", seed=99).generate_for_profile(
            self.profile,
            force=False,
            persist=True,
        )
        self.assertTrue(second.cached)
        self.assertEqual(first.bio, second.bio)

    def test_cache_invalidates_when_interests_change(self):
        ProfileGenerator(style="friendly", language="en", seed=3).generate_for_profile(
            self.profile, force=True, persist=True
        )
        self.profile.lifestyle_tags = ["reading", "coding"]
        self.profile.save(update_fields=["lifestyle_tags", "updated_at"])
        again = ProfileGenerator(style="friendly", language="en", seed=3).generate_for_profile(
            self.profile, force=False, persist=True
        )
        self.assertFalse(again.cached)

    def test_api_generate_endpoint(self):
        client = APIClient()
        client.force_authenticate(user=self.user)
        response = client.post(
            "/api/profile/generate/",
            {"style": "friendly", "language": "en", "force": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("bio", response.data)
        self.assertIn("future_goals", response.data)
        self.assertIn("looking_for", response.data)
