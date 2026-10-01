"""Conversation starters written from the other person's profile.

Candidates come from real profile data (shared and personal interests, bio,
job, education, city, relationship goal, future goals, habits, languages).
Each belongs to a category; categories are ranked by a learned reply rate
(first messages in real conversations that got an answer, smoothed with a
prior so a few examples can't dominate) plus how specific the line is.
"""
from __future__ import annotations

import hashlib
import re

from matching.compatibility import interests
from matching.recommendation.scoring import _parse_pref_values

# Prior reply rates (before any data): specific, personal openers do better.
PRIOR = {
    "sector": 0.45,
    "bio": 0.62,
    "shared_interest": 0.60,
    "their_interest": 0.55,
    "future": 0.50,
    "work": 0.48,
    "city": 0.46,
    "education": 0.44,
    "lifestyle": 0.44,
    "goal": 0.40,
    "language": 0.40,
    "general": 0.30,
}
PRIOR_STRENGTH = 4  # pseudo-messages behind each prior

KEYWORDS = {
    "work": ("work", "job", "office", "career", "business"),
    "education": ("study", "studied", "college", "university", "degree", "school"),
    "city": ("kathmandu", "pokhara", "lalitpur", "city", "live in", "place", "spot"),
    "goal": ("looking for", "relationship", "serious", "marriage"),
    "future": ("future", "plan", "dream", "goal", "someday"),
    "lifestyle": ("gym", "workout", "vegetarian", "coffee", "tea", "weekend", "morning"),
    "language": ("language", "nepali", "hindi", "newari", "english"),
}

TEMPLATES = {
    "shared_interest": [
        "We both love {x}! What got you into it?",
        "Fellow {x} fan here. What's your best {x} memory?",
        "Since we're both into {x}, what's one {x} plan on your list this year?",
    ],
    "their_interest": [
        "I saw you're into {x}. How did you get started?",
        "Your love of {x} caught my eye. What do you enjoy most about it?",
        "I'd love a beginner's tip for {x}. Where should I start?",
    ],
    "bio": [
        'Your bio says "{x}". I have to ask for the story behind that.',
        'I liked "{x}" in your bio. Tell me more?',
    ],
    "work": [
        "What's the best part of being {x}?",
        "How did you end up becoming {x}? Was it always the plan?",
    ],
    "sector": [
        "What's the best part of working in the {x} sector?",
        "How do you like working in the {x} sector?",
    ],
    "education": [
        "What was your favourite part of studying {x}?",
        "Would you study {x} again if you could choose now?",
    ],
    "city": [
        "What's your favourite hidden spot in {x}?",
        "If I visited {x} for a day, where should I eat?",
    ],
    "goal": ["What does a great relationship look like to you?"],
    "future": [
        'You mentioned "{x}" as a future goal. What\'s the first step?',
    ],
    "lifestyle": [
        "Morning person or night owl?",
        "What does a perfect weekend look like for you?",
    ],
    "language": ["Which languages do you speak at home? Teach me a word?"],
    "general": [
        "What's something that made you smile this week?",
        "Tea or coffee, and where's the best cup in town?",
    ],
}


def categorize(text: str) -> str:
    """Rough category of a first message (used to learn reply rates)."""
    low = (text or "").lower()
    if "bio" in low:
        return "bio"
    if "we both" in low or "fellow" in low or "same" in low:
        return "shared_interest"
    if "into " in low or "you like" in low or "your profile" in low:
        return "their_interest"
    for cat, words in KEYWORDS.items():
        if any(w in low for w in words):
            return cat
    return "general"


def learned_rate(cat: str, stats: dict) -> float:
    s = stats.get(cat, {})
    prior = PRIOR.get(cat, 0.3)
    return (s.get("replied", 0) + prior * PRIOR_STRENGTH) / (s.get("sent", 0) + PRIOR_STRENGTH)


def _pick(options: list[str], seed: str) -> str:
    h = int(hashlib.sha1(seed.encode()).hexdigest(), 16)
    return options[h % len(options)]


def _bio_snippet(bio: str) -> str | None:
    text = re.sub(r"\s+", " ", (bio or "").strip())
    if len(text) < 12:
        return None  # too short to quote meaningfully
    first = re.split(r"(?<=[.!?])\s", text)[0]
    return first if len(first) <= 60 else first[:57].rsplit(" ", 1)[0] + "..."


def build_starters(viewer_profile, other_profile, shared: list[str], stats: dict | None = None, *, seed: str = "", limit: int = 4) -> list[str]:
    """Up to ``limit`` openers the viewer could send, about the other person."""
    stats = stats or {}
    other_int = interests(other_profile)
    prefs = _parse_pref_values(other_profile.pref_values)
    candidates: list[tuple[float, str, str]] = []  # (score, category, text)

    def add(cat: str, value: str | None, specificity: float):
        if not value:
            return
        text = _pick(TEMPLATES[cat], f"{seed}:{cat}:{value}").replace("{x}", value)
        candidates.append((learned_rate(cat, stats) + specificity, cat, text))

    for i, tag in enumerate(shared[:2]):
        add("shared_interest", tag.lower(), 0.15 - i * 0.05)
    shared_low = {s.lower() for s in shared}
    theirs = [v for k, v in other_int.items() if k not in shared_low]
    for i, tag in enumerate(theirs[:2]):
        add("their_interest", tag.lower(), 0.10 - i * 0.05)
    add("bio", _bio_snippet(other_profile.bio or ""), 0.12)

    occ = (other_profile.occupation or "").strip()
    if len(occ) > 2 and not occ.isdigit():
        role = occ.lower()
        add("work", f"{'an' if role[0] in 'aeiou' else 'a'} {role}", 0.06)
    elif other_profile.work_preference:
        add("sector", other_profile.work_preference.lower(), 0.02)
    edu = (other_profile.education or "").strip()
    if len(edu) > 2 and not edu.isdigit():
        add("education", edu, 0.04)
    city = (other_profile.location or "").split(",")[0].strip()
    city = re.sub(r"\s+(Sub-?Metropolitan City|Metropolitan City|Municipality)$", "", city, flags=re.I)
    if city:
        add("city", city, 0.03)
    future = (prefs.get("futureGoals") or "").strip()
    if future:
        add("future", future[:50], 0.08)
    if other_profile.relationship_goal:
        add("goal", "goal", 0.0)
    langs = prefs.get("languages") or []
    if langs:
        add("language", "lang", 0.0)
    add("lifestyle", "weekend", -0.02)
    add("general", "general", -0.05)

    # best first, one per category, then fill
    candidates.sort(key=lambda c: -c[0])
    out, used = [], set()
    for score, cat, text in candidates:
        if cat in used or text in out:
            continue
        out.append(text)
        used.add(cat)
        if len(out) >= limit:
            return out
    for score, cat, text in candidates:
        if text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out
