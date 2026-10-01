"""Tests for Duo's own match model (matching/ml)."""
from types import SimpleNamespace

import numpy as np
from django.test import SimpleTestCase

from matching.ml.features import ALL_NAMES
from matching.ml.model import MatchModel, auc, cross_validate
from matching.ml.starters import build_starters, categorize, learned_rate


class AucTests(SimpleTestCase):
    def test_perfect_and_random(self):
        y = np.array([0, 0, 1, 1])
        self.assertEqual(auc(y, np.array([0.1, 0.2, 0.8, 0.9])), 1.0)
        self.assertEqual(auc(y, np.array([0.5, 0.5, 0.5, 0.5])), 0.5)
        self.assertIsNone(auc(np.array([1, 1]), np.array([0.2, 0.3])))


class ModelTests(SimpleTestCase):
    def _data(self, n=200, seed=0):
        rng = np.random.default_rng(seed)
        X = rng.random((n, len(ALL_NAMES)))
        # label depends on feature 0 ("goal") only
        y = (X[:, 0] + 0.1 * rng.standard_normal(n) > 0.5).astype(float)
        return X, y, np.ones(n)

    def test_learns_signal_and_explains_it(self):
        X, y, w = self._data()
        model = MatchModel.fit(X, y, w)
        self.assertGreater(auc(y, model.predict_proba_matrix(X)), 0.9)
        top = max(range(len(ALL_NAMES)), key=lambda i: abs(model.weights[i]))
        self.assertEqual(ALL_NAMES[top], "goal")
        contrib = model.contributions(list(X[0]))
        self.assertEqual(set(contrib), set(ALL_NAMES))

    def test_cross_validation_and_payload_roundtrip(self):
        X, y, w = self._data()
        self.assertGreater(cross_validate(X, y, w)["cv_auc"], 0.85)
        model = MatchModel.fit(X, y, w)
        again = MatchModel.from_payload(model.to_payload())
        self.assertAlmostEqual(again.predict_proba(list(X[3])), model.predict_proba(list(X[3])))
        self.assertTrue(1 <= model.score_100(0.5) <= 99)

    def test_payload_with_old_features_is_rejected(self):
        self.assertIsNone(MatchModel.from_payload({"feature_names": ["old"]}))


def _profile(**kw):
    base = dict(
        full_name="Asha Rai", age=25, bio="", lifestyle_tags=[], pref_values="", occupation="",
        education="", location="Pokhara, Nepal", relationship_goal="", work_preference="",
    )
    base.update(kw)
    return SimpleNamespace(**base)


class StarterTests(SimpleTestCase):
    def test_uses_other_persons_profile(self):
        me = _profile(full_name="Bishal", lifestyle_tags=["Hiking"])
        other = _profile(
            bio="Yoga instructor who loves sunrise hikes.",
            lifestyle_tags=["Hiking", "Photography"],
            occupation="Teacher",
        )
        starters = build_starters(me, other, ["Hiking"], {}, seed="t")
        joined = " ".join(starters).lower()
        self.assertEqual(len(starters), 4)
        self.assertIn("hiking", joined)
        self.assertIn("yoga instructor", joined)
        self.assertEqual(len(set(starters)), 4)

    def test_sparse_profile_still_gets_starters(self):
        starters = build_starters(_profile(), _profile(location=""), [], {}, seed="t")
        self.assertGreaterEqual(len(starters), 2)

    def test_learned_rate_uses_data(self):
        self.assertGreater(learned_rate("general", {"general": {"sent": 20, "replied": 18}}), learned_rate("general", {}))
        self.assertEqual(categorize("Your bio made me laugh"), "bio")
