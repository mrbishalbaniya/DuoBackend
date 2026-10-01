"""Tests for Duo's own About-section writing assistant."""
from unittest import mock

from django.test import SimpleTestCase

from accounts import writing_assistant as wa

DRAFT = {
    "full_name": "Asha Rai",
    "age": "26",
    "location": "Pokhara Metropolitan City, Nepal",
    "occupation": "Teacher",
    "relationship_goal": "serious",
    "lifestyleTagsText": "Hiking, Photography, introvert, smoking:no",
    "languages": ["Nepali", "English"],
    "work_preference": "Government",
}


@mock.patch.object(wa, "ranker", return_value=(wa.PRIOR_WEIGHTS, {"source": "prior"}))
class WritingAssistantTests(SimpleTestCase):
    def test_bio_uses_profile_facts(self, _):
        out = wa.suggest("bio", DRAFT, user_id=1)
        text = " ".join(out["suggestions"]).lower()
        self.assertEqual(len(out["suggestions"]), 3)
        self.assertIn("teacher", text)
        self.assertIn("pokhara", text)
        self.assertNotIn("metropolitan", text)
        self.assertIn("hiking", text)

    def test_all_fields_and_variants(self, _):
        for field in wa.FIELDS:
            first = wa.suggest(field, DRAFT, user_id=1)["suggestions"]
            self.assertTrue(first)
            for s in first:
                self.assertLessEqual(len(s), wa.MAX_LEN[field])
                self.assertNotIn(" .", s)

    def test_sparse_profile_gets_honest_fallbacks(self, _):
        out = wa.suggest("bio", {"full_name": "Sam"}, user_id=2)
        self.assertEqual(len(out["suggestions"]), 3)

    def test_unknown_field_rejected(self, _):
        with self.assertRaises(ValueError):
            wa.suggest("password", DRAFT)
