"""Duo's own writing assistant for the profile "About" section.

Writes Bio, Looking for and Future goals suggestions from the member's profile
data (job, education, city, interests, personality, habits, languages,
relationship goal and partner preferences). No external AI service.

How it works
------------
1. **Composer**: several styles (warm, playful, straightforward) each build a
   candidate from phrase variants filled with real profile facts. Missing
   facts are skipped, never invented.
2. **Learned ranker**: a small ridge regression learns, from real Duo
   profiles, which bio traits go with a higher share of likes received
   (length, mentioning interests / job / city, ending with a question, ...).
   Candidates are ranked by it; with too little data it falls back to priors.

Suggestions change when the profile changes, and ``variant`` gives a fresh set.
"""
from __future__ import annotations

import hashlib
import random
import re

import numpy as np
from django.core.cache import cache

FIELDS = ("bio", "looking_for", "future_goals")
MAX_LEN = {"bio": 300, "looking_for": 200, "future_goals": 200}

PERSONALITY = {"introvert", "ambivert", "extrovert"}
DIETS = {"vegetarian", "vegan", "non-vegetarian", "eggetarian"}
NON_INTEREST = PERSONALITY | DIETS | {"active", "balanced", "relaxed", "non-smoker"}

GOAL_TEXT = {
    "serious": "a serious relationship",
    "long-term": "a long-term relationship",
    "long_term": "a long-term relationship",
    "marriage": "marriage",
    "casual": "something casual and fun",
    "friendship": "friendship first",
    "not_sure": "whatever feels right",
}

RANKER_KEY = "writing_assistant:ranker:v1"
RANKER_TTL = 60 * 60  # retrain hourly at most
FEATURES = ["len_short", "len_mid", "len_long", "interests", "job", "city", "question", "goal", "personality"]
PRIOR_WEIGHTS = np.array([-0.2, 0.3, 0.05, 0.35, 0.2, 0.1, 0.15, 0.1, 0.1])


# ------------------------------------------------------------------ facts
def _clean(text) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _useful(text: str) -> bool:
    """Skip placeholder values such as '11' or 'n/a'."""
    t = _clean(text)
    return len(t) > 2 and not t.isdigit() and t.lower() not in {"n/a", "na", "none", "-"}


def facts_from_draft(draft: dict) -> dict:
    tags = [t.strip() for t in str(draft.get("lifestyleTagsText") or "").split(",") if t.strip()]
    low = [t.lower() for t in tags]
    interests = [t for t in tags if ":" not in t and t.lower() not in NON_INTEREST]
    habit = {t.split(":", 1)[0]: t.split(":", 1)[1] for t in low if ":" in t}
    city = _clean(draft.get("location")).split(",")[0]
    city = re.sub(r"\s+(Sub-?Metropolitan City|Metropolitan City|Municipality)$", "", city, flags=re.I)
    goal = str(draft.get("relationship_goal") or "").lower()
    return {
        "first_name": _clean(draft.get("full_name")).split(" ")[0],
        "age": draft.get("age"),
        "city": city if _useful(city) else "",
        "job": _clean(draft.get("occupation")) if _useful(draft.get("occupation")) else "",
        "company": _clean(draft.get("company")) if _useful(draft.get("company")) else "",
        "study": _clean(draft.get("fieldOfStudy") or draft.get("education")),
        "work_pref": _clean(draft.get("work_preference")).lower(),
        "interests": interests[:6],
        "personality": next((t for t in low if t in PERSONALITY), ""),
        "diet": next((t for t in low if t in DIETS), ""),
        "exercise": habit.get("exercise", ""),
        "smoking": habit.get("smoking", ""),
        "drinking": habit.get("drinking", ""),
        "languages": [l for l in (draft.get("languages") or []) if _useful(l)][:3],
        "goal": GOAL_TEXT.get(goal, ""),
        "pref_goal": GOAL_TEXT.get(str(draft.get("pref_relationship_goal") or "").lower(), ""),
        "pref_age": (draft.get("pref_age_min"), draft.get("pref_age_max")),
    }


def _join(items: list[str]) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _a(word: str) -> str:
    return ("an " if word[:1].lower() in "aeiou" else "a ") + word


# ------------------------------------------------------------------ composers
def _bio_candidates(f: dict, rng: random.Random) -> list[str]:
    ints = [i.lower() for i in f["interests"]]
    job = f["job"].lower() if f["job"] else ""
    out = []

    # warm
    parts = []
    if job and f["city"]:
        parts.append(rng.choice([f"{_a(job).capitalize()} based in {f['city']}.", f"{f['city']}-based {job}."]))
    elif job:
        parts.append(f"{_a(job).capitalize()} who loves what I do.")
    elif f["city"]:
        parts.append(f"Living and loving life in {f['city']}.")
    if ints:
        parts.append(rng.choice([
            f"You'll usually find me making time for {_join(ints[:3])}.",
            f"Big fan of {_join(ints[:3])}.",
            f"My happy place: {_join(ints[:3])}.",
        ]))
    if f["personality"]:
        parts.append({
            "introvert": "A bit of an introvert who opens up over good conversation.",
            "extrovert": "An extrovert who never says no to a new plan.",
            "ambivert": "Equally happy at a lively dinner or a quiet night in.",
        }[f["personality"]])
    if f["goal"]:
        parts.append(f"Here for {f['goal']}.")
    out.append(" ".join(parts))

    # playful
    parts = []
    if ints:
        parts.append(rng.choice([
            f"Part-time {ints[0]} enthusiast, full-time good company.",
            f"Ask me about {ints[0]} and I'll talk for hours.",
        ]))
    if job:
        parts.append(f"By day, I'm {_a(job)}{' at ' + f['company'] if f['company'] else ''}.")
    if len(ints) > 1:
        parts.append(f"By weekend, {_join(ints[1:3])}.")
    if f["diet"] == "vegetarian" or f["diet"] == "vegan":
        parts.append("Always hunting for the best veg momo in town.")
    elif f["city"]:
        parts.append(f"Always hunting for the best food spot in {f['city']}.")
    parts.append(rng.choice(["What's your favourite way to spend a Saturday?", "Tell me your best travel story?"]))
    if len(parts) > 1:
        out.append(" ".join(parts))

    # straightforward
    parts = []
    who = ", ".join(x for x in [f"{f['age']}" if f["age"] else "", job] if x)
    if who:
        parts.append(f"{who.capitalize()}{' in ' + f['city'] if f['city'] else ''}.")
    if f["languages"]:
        parts.append(f"I speak {_join(f['languages'])}.")
    if ints:
        parts.append(f"Interests: {', '.join(ints[:4])}.")
    habits = []
    if f["smoking"] == "no":
        habits.append("non-smoker")
    if f["exercise"] in {"regularly", "daily", "often", "yes"}:
        habits.append("working out regularly")
    if habits:
        text = _join(habits)
        parts.append(text[0].upper() + text[1:] + ".")
    if f["goal"]:
        parts.append(f"Looking for {f['goal']} with someone genuine.")
    out.append(" ".join(parts))

    # thin profiles: honest, simple openers that invite a conversation
    out += [
        "New here and happy to take things one conversation at a time. Good food, long walks and honest people make my day.",
        "Easygoing, curious and always up for a good chat. Ask me about my favourite place to eat.",
        "Family matters to me, laughter keeps me going and I'm here to meet someone genuine.",
    ]
    return out


def _looking_for_candidates(f: dict, rng: random.Random) -> list[str]:
    ints = [i.lower() for i in f["interests"]]
    goal = f["pref_goal"] or f["goal"]
    lo, hi = f["pref_age"]
    out = [
        " ".join(x for x in [
            "Someone kind, honest and easy to talk to",
            f"who'd enjoy {_join(ints[:2])} with me" if ints else "",
            f"and is ready for {goal}." if goal else ".",
        ] if x).replace(" .", "."),
        " ".join(x for x in [
            rng.choice(["A genuine person with a good sense of humour", "Someone warm, curious and grounded"]),
            f"who values family and {f['languages'][0]} conversations" if f["languages"] else "who values family",
            f"and wants {goal}." if goal else "and wants to build something real.",
        ] if x),
        " ".join(x for x in [
            "Looking for a partner in crime",
            f"for {ints[0]} weekends" if ints else "for spontaneous plans",
            f"and slow evenings in {f['city']}" if f["city"] else "and slow evenings in",
            f", ideally {lo}-{hi}." if lo and hi else ".",
        ] if x).replace(" ,", ",").replace(" .", "."),
    ]
    return out


def _future_goals_candidates(f: dict, rng: random.Random) -> list[str]:
    job = f["job"].lower() if f["job"] else ""
    ints = [i.lower() for i in f["interests"]]
    travel = any(i in {"travel", "travelling", "traveling", "hiking", "trekking"} for i in ints)
    other = [i for i in ints if i not in {"travel", "travelling", "traveling"}]
    out = [
        " ".join(x for x in [
            f"Grow in my career as {_a(job)}" if job else "Keep growing in my career",
            "and build a warm, happy home with the right person.",
        ] if x),
        " ".join(x for x in [
            "Travel more of Nepal and beyond," if travel else "See more of the world,",
            f"keep making time for {other[0]}," if other else "stay curious,",
            f"and settle down {'in ' + f['city'] if f['city'] else 'close to family'}.",
        ] if x),
        " ".join(x for x in [
            f"Build something of my own in the {f['work_pref']} sector," if f["work_pref"] else "Work toward financial independence,",
            "stay close to family",
            f"and find {f['goal']}." if f["goal"] else "and share the journey with a partner.",
        ] if x),
        "Stay healthy, keep learning something new every year and raise a family full of laughter.",
        " ".join(x for x in [
            f"Keep {ints[0]} in my life," if ints else "Keep my hobbies alive,",
            "save for a home of our own and take one big trip every year.",
        ] if x),
    ]
    return out


COMPOSERS = {"bio": _bio_candidates, "looking_for": _looking_for_candidates, "future_goals": _future_goals_candidates}


# ------------------------------------------------------------------ learned ranker
def _text_features(text: str, f: dict) -> np.ndarray:
    words = len(text.split())
    low = text.lower()
    return np.array([
        1.0 if words < 12 else 0.0,
        1.0 if 12 <= words <= 45 else 0.0,
        1.0 if words > 45 else 0.0,
        min(sum(1 for i in f["interests"] if i.lower() in low), 3) / 3,
        1.0 if f["job"] and f["job"].lower() in low else 0.0,
        1.0 if f["city"] and f["city"].lower() in low else 0.0,
        1.0 if "?" in text else 0.0,
        1.0 if any(w in low for w in ("relationship", "marriage", "serious", "settle")) else 0.0,
        1.0 if any(w in low for w in ("introvert", "extrovert", "quiet night", "lively")) else 0.0,
    ])


def _train_ranker() -> tuple[np.ndarray, dict]:
    """Ridge regression of like-rate on bio traits across real profiles."""
    from accounts.models import Profile
    from matching.models import Swipe
    from django.db.models import Count, Q

    stats = (
        Swipe.objects.values("to_user_id")
        .annotate(total=Count("id"), likes=Count("id", filter=~Q(action="SKIP")))
        .filter(total__gte=3)
    )
    rate = {s["to_user_id"]: s["likes"] / s["total"] for s in stats}
    X, y = [], []
    for p in Profile.objects.filter(user_id__in=list(rate)).exclude(bio=""):
        facts = {
            "interests": [t for t in (p.lifestyle_tags or []) if ":" not in str(t)],
            "job": p.occupation or "",
            "city": (p.location or "").split(",")[0],
        }
        X.append(_text_features(p.bio, facts))
        y.append(rate[p.user_id])
    info = {"trained_on": len(y)}
    if len(y) < 25:
        info["source"] = "prior"
        return PRIOR_WEIGHTS, info
    X, y = np.asarray(X), np.asarray(y)
    y = y - y.mean()
    lam = 5.0
    w = np.linalg.solve(X.T @ X + lam * np.eye(X.shape[1]), X.T @ y)
    # blend with priors so a small sample can't flip sensible defaults
    blend = len(y) / (len(y) + 100)
    info["source"] = "learned"
    return blend * w * 10 + (1 - blend) * PRIOR_WEIGHTS, info


def ranker() -> tuple[np.ndarray, dict]:
    cached = cache.get(RANKER_KEY)
    if cached:
        return np.asarray(cached[0]), cached[1]
    w, info = _train_ranker()
    cache.set(RANKER_KEY, (w.tolist(), info), RANKER_TTL)
    return w, info


# ------------------------------------------------------------------ entry point
def suggest(field: str, draft: dict, *, variant: int = 0, user_id: int | None = None, limit: int = 3) -> dict:
    if field not in FIELDS:
        raise ValueError(f"Unknown field {field!r}")
    f = facts_from_draft(draft or {})
    seed = int(hashlib.sha1(f"{user_id}:{field}:{variant}".encode()).hexdigest(), 16)
    rng = random.Random(seed)

    candidates = []
    for _ in range(3):  # a few rounds of phrase choices for variety
        candidates += COMPOSERS[field](f, rng)
    cleaned = []
    for text in candidates:
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"\s+([.,?])", r"\1", text).replace("..", ".")
        if len(text.split()) < 4 or text in cleaned:
            continue
        cleaned.append(text[: MAX_LEN[field]])

    w, info = ranker()
    scored = sorted(cleaned, key=lambda t: -float(_text_features(t, f) @ w))
    if variant and scored:  # "More ideas": rotate through the ranked list
        offset = (variant * limit) % len(scored)
        scored = scored[offset:] + scored[:offset]
    # keep variety: first pick the best, then prefer different openings
    picks = []
    for t in scored:
        if all(t.split()[:2] != p.split()[:2] for p in picks):
            picks.append(t)
        if len(picks) == limit:
            break
    for t in scored:
        if len(picks) == limit:
            break
        if t not in picks:
            picks.append(t)

    used = [k for k in ("job", "city", "interests", "personality", "goal", "languages") if f.get(k)]
    return {"field": field, "suggestions": picks, "based_on": used, "model": info}
