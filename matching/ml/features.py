"""Pair features for Duo's own match model.

Every feature is a number in [0, 1] computed from two Profile objects. Missing
information becomes a neutral 0.5 plus a "known" indicator, so the model can
learn that an empty field is not the same as a mismatch. Most features reuse
the deterministic engine in ``matching.compatibility`` so the model and the
on-screen pillar scores describe the same facts.
"""
from __future__ import annotations

from dataclasses import dataclass

from matching.compatibility import (
    career_factors,
    dice,
    interests,
    lifestyle_factors,
    values_factors,
)
from matching.recommendation.scoring import _parse_pref_values

# Near-synonyms so "Hiking" and "Trekking" count as a shared interest.
INTEREST_SYNONYMS: list[set[str]] = [
    {"hiking", "trekking", "mountaineering", "trekking & hiking", "outdoors"},
    {"music", "singing", "guitar", "concerts", "playing music"},
    {"travel", "travelling", "traveling", "exploring", "road trips"},
    {"reading", "books", "literature", "poetry"},
    {"cooking", "baking", "food", "foodie"},
    {"fitness", "gym", "workout", "running", "sports"},
    {"movies", "films", "cinema", "series", "netflix"},
    {"photography", "photos", "camera"},
    {"dancing", "dance"},
    {"gaming", "video games", "esports"},
    {"yoga", "meditation", "mindfulness"},
    {"art", "painting", "drawing", "sketching"},
    {"volunteering", "philanthropy", "charity", "social work"},
]


def _canon(tag: str) -> str:
    low = tag.strip().lower()
    for group in INTEREST_SYNONYMS:
        if low in group:
            return sorted(group)[0]
    return low


def shared_interests(a, b) -> list[str]:
    """Shared interests including synonyms, using person A's wording."""
    ia, ib = interests(a), interests(b)
    canon_b = {_canon(t) for t in ib}
    out = [orig for low, orig in ia.items() if _canon(low) in canon_b]
    return sorted(set(out))


# name -> pillar (used for explanations and pillar notes)
FEATURES: dict[str, str] = {
    "goal": "values",
    "religion": "values",
    "caste": "values",
    "languages": "values",
    "smoking": "lifestyle",
    "drinking": "lifestyle",
    "exercise": "lifestyle",
    "diet": "lifestyle",
    "personality": "lifestyle",
    "age_fit": "lifestyle",
    "distance": "lifestyle",
    "age_gap": "lifestyle",
    "education": "career",
    "occupation": "career",
    "work": "career",
    "hobbies": "hobbies",
    "shared_count": "hobbies",
    "profile_depth": "values",
}
FEATURE_NAMES: list[str] = list(FEATURES)
# "known" indicators let the model tell missing data from a real mismatch
KNOWN_NAMES: list[str] = [f"{n}_known" for n in FEATURE_NAMES if n not in {"age_gap", "shared_count", "profile_depth"}]
ALL_NAMES: list[str] = FEATURE_NAMES + KNOWN_NAMES


@dataclass
class PairFeatures:
    values: dict[str, float]  # all ALL_NAMES keys
    raw: dict[str, float | None]  # factor values before neutral fill (None = unknown)

    def vector(self) -> list[float]:
        return [self.values[n] for n in ALL_NAMES]


def _depth(p) -> float:
    """How complete a profile is (0..1): bio, interests, goal, education, job, religion."""
    checks = [
        bool((p.bio or "").strip()),
        len(interests(p)) >= 3,
        bool(p.relationship_goal),
        bool(p.education),
        bool(p.occupation),
        bool(p.religion),
    ]
    return sum(checks) / len(checks)


def pair_features(a, b) -> PairFeatures:
    pa, pb = _parse_pref_values(a.pref_values), _parse_pref_values(b.pref_values)
    v = values_factors(a, b, pa, pb)
    life = lifestyle_factors(a, b)
    c = career_factors(a, b, pa, pb)
    ia, ib = interests(a), interests(b)
    hobbies = dice({_canon(t) for t in ia}, {_canon(t) for t in ib})

    raw: dict[str, float | None] = {
        "goal": v["goal"],
        "religion": v["religion"],
        "caste": v["caste"],
        "languages": v["languages"],
        "smoking": life["smoking"],
        "drinking": life["drinking"],
        "exercise": life["exercise"],
        "diet": life["diet"],
        "personality": life["personality"],
        "age_fit": life["age"],
        "distance": life["distance"],
        "education": c["education"],
        "occupation": c["occupation"],
        "work": c["work"],
        "hobbies": hobbies,
    }
    values: dict[str, float] = {}
    for name, val in raw.items():
        values[name] = 0.5 if val is None else float(val)
        values[f"{name}_known"] = 0.0 if val is None else 1.0

    gap = abs((a.age or 0) - (b.age or 0)) if a.age and b.age else None
    values["age_gap"] = 0.5 if gap is None else max(0.0, 1 - min(gap, 15) / 15)
    values["shared_count"] = min(len(shared_interests(a, b)), 5) / 5
    values["profile_depth"] = (_depth(a) + _depth(b)) / 2
    return PairFeatures(values=values, raw=raw)
