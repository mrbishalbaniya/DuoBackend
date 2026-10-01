"""Compatibility scoring for a matched pair (own module, no external library).

Replaces the earlier random placeholder scores. Every number shown on the
"Match Insights" screen is now computed from the two profiles:

    values     (35%)  relationship goal, religion stance, caste stance, shared languages
    lifestyle  (25%)  habits (smoking, drinking, exercise, diet), personality, two-way age fit, distance
    career     (25%)  education level, occupation group, work preference
    hobbies    (15%)  Sørensen–Dice overlap of interest tags

Each sub-score is the mean of the factors that are known for BOTH people
(0.0–1.0), scaled to 0–100. A factor that is missing for either person is left
out; if nothing is known for a dimension it scores a neutral 50, so sparse
profiles are neither rewarded nor punished. The overall score is the weighted
sum of the four dimensions. The function is deterministic: the same two
profiles always give the same result.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from accounts.geo import haversine_km, profile_coordinates
from matching.recommendation.scoring import OCCUPATION_KEYWORDS, _goal_fit, _parse_pref_values

WEIGHTS = {"values": 0.35, "lifestyle": 0.25, "career": 0.25, "hobbies": 0.15}
NEUTRAL = 0.5

# lifestyle tags that are not hobbies
PERSONALITY = {"introvert", "ambivert", "extrovert"}
ENERGY = {"active", "balanced", "relaxed"}
HABIT_PREFIXES = ("smoking:", "drinking:", "exercise:", "marital:", "diet:")
DIET_TAGS = {"vegetarian", "vegan", "non-vegetarian", "eggetarian"}
NON_HOBBY = PERSONALITY | ENERGY | DIET_TAGS | {"non-smoker"}

# ordered education levels (keywords matched in lower-case text)
EDUCATION_LEVELS = [
    (0, ("see", "slc", "school")),
    (1, ("+2", "plus two", "higher secondary", "intermediate", "a level", "a-level")),
    (2, ("diploma",)),
    (3, ("bachelor", "bba", "bca", "bsc", "b.sc", "be ", "b.e", "bbs", "bed", "mbbs", "llb", "ba ")),
    (4, ("master", "mba", "msc", "m.sc", "ma ", "me ", "m.e", "mbs")),
    (5, ("phd", "ph.d", "doctorate")),
]

OPEN_ANSWERS = {"yes", "open", "preferred", "depends", "maybe"}


@dataclass
class CompatibilityResult:
    compatibility_score: int
    values_score: int
    lifestyle_score: int
    career_score: int
    hobbies_score: int
    shared_interests: list[str] = field(default_factory=list)
    spark_factors: list[str] = field(default_factory=list)
    vision_insight: str = ""
    communication_insight: str = ""

    def as_match_fields(self) -> dict:
        return {
            "compatibility_score": self.compatibility_score,
            "values_score": self.values_score,
            "lifestyle_score": self.lifestyle_score,
            "career_score": self.career_score,
            "hobbies_score": self.hobbies_score,
            "shared_interests": self.shared_interests,
            "spark_factors": self.spark_factors,
            "vision_insight": self.vision_insight,
            "communication_insight": self.communication_insight,
        }


# ------------------------------------------------------------------ helpers
def _tags(profile) -> list[str]:
    return [str(t).strip() for t in (profile.lifestyle_tags or []) if str(t).strip()]


def interests(profile) -> dict[str, str]:
    """Hobby/interest tags, keyed by lower-case name (value keeps original case)."""
    out = {}
    for t in _tags(profile):
        low = t.lower()
        if ":" in low or low in NON_HOBBY:
            continue
        out[low] = t
    return out


def dice(a: set, b: set) -> float | None:
    """Sørensen–Dice coefficient 2|A∩B| / (|A|+|B|); None when either set is empty."""
    if not a or not b:
        return None
    return 2 * len(a & b) / (len(a) + len(b))


def _habit(profile, prefix: str) -> str | None:
    for t in _tags(profile):
        low = t.lower()
        if low.startswith(prefix):
            return low.split(":", 1)[1]
    if prefix == "smoking:" and any(t.lower() == "non-smoker" for t in _tags(profile)):
        return "no"
    return None


def _one_of(profile, options: set) -> str | None:
    return next((t.lower() for t in _tags(profile) if t.lower() in options), None)


def _habit_fit(a: str | None, b: str | None, *, strict: bool) -> float | None:
    """1 = same, 0.5 = partly compatible, 0 = clash (only for strict habits like smoking)."""
    if a is None or b is None:
        return None
    if a == b:
        return 1.0
    if strict and "no" in (a, b) and {"yes", "regularly", "often"} & {a, b}:
        return 0.0
    return 0.5


def _education_level(profile, prefs: dict) -> int | None:
    text = f" {prefs.get('educationLevel', '')} {profile.education or ''} ".lower()
    found = None
    for level, words in EDUCATION_LEVELS:
        if any(w in text for w in words):
            found = level
    return found


def _occupation_group(profile) -> str | None:
    text = f" {(profile.occupation or '').lower()} "
    if not text.strip():
        return None
    for group, words in OCCUPATION_KEYWORDS.items():
        if any(w in text for w in words):
            return group
    return "other"


def _age_fit(a, b) -> float | None:
    """Two-way age fit: 1 if each is inside the other's preferred range, 0.5 if one is."""
    if not a.age or not b.age:
        return None
    hits = 0
    for viewer, other in ((a, b), (b, a)):
        lo, hi = viewer.pref_age_min, viewer.pref_age_max
        if lo and hi and lo <= other.age <= hi:
            hits += 1
    return hits / 2


def _distance_fit(a, b) -> tuple[float | None, float | None]:
    try:
        ca = profile_coordinates(a.location, a.user_id, a.pref_values)
        cb = profile_coordinates(b.location, b.user_id, b.pref_values)
    except Exception:  # pragma: no cover - defensive, coordinates are best effort
        return None, None
    if not a.location or not b.location:
        return None, None
    km = haversine_km(ca, cb)
    limit = min(a.pref_max_distance_km or 50, b.pref_max_distance_km or 50)
    if km <= 25:
        return 1.0, km
    if km <= limit:
        return 0.7, km
    return 0.3, km


def _mean(values: list[float | None]) -> float:
    known = [v for v in values if v is not None]
    return sum(known) / len(known) if known else NEUTRAL


def _pct(x: float) -> int:
    return int(round(max(0.0, min(1.0, x)) * 100))


# ------------------------------------------------------------------ dimensions
def values_factors(a, b, pa: dict, pb: dict) -> dict[str, float | None]:
    ga, gb = (a.relationship_goal or "").strip(), (b.relationship_goal or "").strip()
    goal = _goal_fit(ga, gb) if ga and gb else None

    ra, rb = (a.religion or "").strip().lower(), (b.religion or "").strip().lower()
    religion = None
    if ra and rb:
        if ra == rb:
            religion = 1.0
        else:
            open_a = (pa.get("interReligion") or "").strip().lower() in OPEN_ANSWERS
            open_b = (pb.get("interReligion") or "").strip().lower() in OPEN_ANSWERS
            religion = 0.8 if (open_a and open_b) else 0.5 if (open_a or open_b) else 0.2

    ca, cb = (pa.get("caste") or "").strip().lower(), (pb.get("caste") or "").strip().lower()
    caste = None
    if ca and cb:
        if ca == cb:
            caste = 1.0
        else:
            open_a = (pa.get("interCaste") or "").strip().lower() in OPEN_ANSWERS
            open_b = (pb.get("interCaste") or "").strip().lower() in OPEN_ANSWERS
            caste = 0.8 if (open_a and open_b) else 0.4

    la = {str(x).strip().lower() for x in (pa.get("languages") or []) if str(x).strip()}
    lb = {str(x).strip().lower() for x in (pb.get("languages") or []) if str(x).strip()}
    languages = dice(la, lb)
    return {"goal": goal, "religion": religion, "caste": caste, "languages": languages}


def lifestyle_factors(a, b) -> dict[str, float | None]:
    dist, _ = _distance_fit(a, b)
    return {
        "smoking": _habit_fit(_habit(a, "smoking:"), _habit(b, "smoking:"), strict=True),
        "drinking": _habit_fit(_habit(a, "drinking:"), _habit(b, "drinking:"), strict=True),
        "exercise": _habit_fit(_habit(a, "exercise:"), _habit(b, "exercise:"), strict=False),
        "diet": _habit_fit(_one_of(a, DIET_TAGS), _one_of(b, DIET_TAGS), strict=False),
        "personality": _habit_fit(_one_of(a, PERSONALITY), _one_of(b, PERSONALITY), strict=False),
        "age": _age_fit(a, b),
        "distance": dist,
    }


def career_factors(a, b, pa: dict, pb: dict) -> dict[str, float | None]:
    ea, eb = _education_level(a, pa), _education_level(b, pb)
    education = None if ea is None or eb is None else 1 - abs(ea - eb) / 5
    oa, ob = _occupation_group(a), _occupation_group(b)
    occupation = None if oa is None or ob is None else (1.0 if oa == ob and oa != "other" else 0.5)
    wa, wb = (a.work_preference or "").strip().lower(), (b.work_preference or "").strip().lower()
    work = None if not wa or not wb else (1.0 if wa == wb else 0.6)
    return {"education": education, "occupation": occupation, "work": work}


# ------------------------------------------------------------------ main entry
def compute_compatibility(a, b) -> CompatibilityResult:
    """Compatibility of two Profile objects (order does not matter)."""
    pa, pb = _parse_pref_values(a.pref_values), _parse_pref_values(b.pref_values)
    ia, ib = interests(a), interests(b)

    v = values_factors(a, b, pa, pb)
    life = lifestyle_factors(a, b)
    c = career_factors(a, b, pa, pb)
    h = dice(set(ia), set(ib))

    dims = {"values": _mean(list(v.values())), "lifestyle": _mean(list(life.values())),
            "career": _mean(list(c.values())), "hobbies": NEUTRAL if h is None else h}
    overall = sum(WEIGHTS[k] * dims[k] for k in WEIGHTS)

    shared = sorted(ia[k] for k in set(ia) & set(ib))
    result = CompatibilityResult(
        compatibility_score=_pct(overall),
        values_score=_pct(dims["values"]),
        lifestyle_score=_pct(dims["lifestyle"]),
        career_score=_pct(dims["career"]),
        hobbies_score=_pct(dims["hobbies"]),
        shared_interests=shared,
    )
    result.spark_factors = _sparks(a, b, v, life, c, shared)
    result.vision_insight = _vision(a, b, v)
    result.communication_insight = _communication(a, b, pa, pb)
    return result


# ------------------------------------------------------------------ explanations (facts only)
def _name(p) -> str:
    return (p.full_name or "").split(" ")[0] or "This person"


def _sparks(a, b, v, life, c, shared) -> list[str]:
    sparks: list[tuple[float, str]] = []
    if len(shared) >= 2:
        sparks.append((0.9 + 0.01 * len(shared), f"Both enjoy {', '.join(shared[:3])}"))
    elif len(shared) == 1:
        sparks.append((0.7, f"Both enjoy {shared[0]}"))
    if v["religion"] == 1.0:
        sparks.append((0.85, f"Share the same religion ({a.religion})"))
    if v["goal"] == 1.0:
        sparks.append((0.88, "Looking for the same kind of relationship"))
    if life["age"] == 1.0:
        sparks.append((0.75, "Each fits the other's preferred age range"))
    if life["distance"] == 1.0:
        sparks.append((0.72, "Live close to each other"))
    if c["education"] is not None and c["education"] >= 0.8:
        sparks.append((0.7, "Similar level of education"))
    if c["work"] == 1.0:
        sparks.append((0.65, f"Both prefer {a.work_preference.lower()} work"))
    if life["smoking"] == 1.0 or life["drinking"] == 1.0:
        sparks.append((0.66, "Matching habits"))
    sparks.sort(key=lambda s: -s[0])
    return [text for _, text in sparks[:3]]


def _vision(a, b, v) -> str:
    parts = []
    if v["goal"] is not None:
        if v["goal"] == 1.0:
            parts.append(f"Both are looking for a {a.relationship_goal} relationship.")
        elif v["goal"] == 0.0:
            parts.append("Your relationship goals differ, so talk about expectations early.")
        else:
            parts.append("Your relationship goals are close but not identical.")
    if v["religion"] is not None:
        parts.append("You share the same religion." if v["religion"] == 1.0
                     else "You follow different religions; your answers show how open each of you is to that.")
    return " ".join(parts) or "Add your relationship goal and religion to see a vision insight."


def _communication(a, b, pa, pb) -> str:
    la = {str(x).strip() for x in (pa.get("languages") or []) if str(x).strip()}
    lb = {str(x).strip() for x in (pb.get("languages") or []) if str(x).strip()}
    common = sorted(la & lb)
    pers_a, pers_b = _one_of(a, PERSONALITY), _one_of(b, PERSONALITY)
    parts = []
    if common:
        parts.append(f"You can talk in {', '.join(common[:3])}.")
    if pers_a and pers_b:
        parts.append(f"{_name(a)} is {pers_a} and {_name(b)} is {pers_b}.")
    return " ".join(parts) or "Add languages and personality to see a communication insight."
