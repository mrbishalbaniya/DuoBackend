"""AI-written Match Insights (Claude), layered on the deterministic engine.

The four percentage scores always come from ``matching.compatibility`` (same
inputs -> same numbers). Claude writes the words around them: a summary, a
note per pillar, spark factors, shared interests (including near-synonyms such
as Hiking/Trekking), a vision and communication deep dive, and conversation
starters.

Results are stored on the Match and reused until either profile (or the
engine's scores) change, so each pair costs one model call per profile edit,
not one per page view. Without credentials, or on any API failure, callers
fall back to the engine's rule-based text.

Only what the insight needs is sent: first names, age, city, bio, interest and
lifestyle tags, goals, education, work, religion and languages. No photos,
contact details, exact coordinates or user ids leave the server.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os

import anthropic
from django.conf import settings
from django.utils import timezone
from pydantic import BaseModel, Field

from matching.compatibility import CompatibilityResult, compute_compatibility, interests
from matching.recommendation.scoring import _parse_pref_values

logger = logging.getLogger("duo.matching.ai")

REFRESH_COOLDOWN_SECONDS = 120
PROMPT_VERSION = "v1"  # bump to regenerate every stored insight after a prompt change


# ------------------------------------------------------------------ output schema
class PillarNotes(BaseModel):
    values: str = Field(description="One sentence on the core-values score, citing concrete facts.")
    lifestyle: str = Field(description="One sentence on the lifestyle & habits score.")
    career: str = Field(description="One sentence on the career & ambition score.")
    hobbies: str = Field(description="One sentence on the hobbies & leisure score.")


class AiMatchInsights(BaseModel):
    summary: str = Field(description="Two warm, specific sentences about this pair. No score numbers.")
    pillar_notes: PillarNotes
    spark_factors: list[str] = Field(description="2-4 short phrases (max 12 words each) naming real common ground.")
    shared_interests: list[str] = Field(
        description="Interests both people have, including close synonyms (e.g. Hiking and Trekking). "
        "Use the wording from the profiles. Empty list if none."
    )
    vision_insight: str = Field(description="2-3 sentences on relationship goals and future plans.")
    communication_insight: str = Field(description="2-3 sentences on how they might talk and connect.")
    conversation_starters: list[str] = Field(
        description="4 friendly first-message questions, each under 20 words, grounded in their profiles."
    )


SYSTEM_PROMPT = """You write the "Match insights" screen of Duo, a dating app used mainly in Nepal.
You get facts about two people who matched, plus compatibility percentages that were already
computed from their profiles. Explain the match in warm, plain English, speaking to both people
together ("you two", or their first names).

Ground every statement in the facts provided. If a fact is missing, don't guess: say less, or
gently suggest what adding it to a profile would reveal. Never invent hobbies, jobs, places,
history or feelings. Keep the tone respectful and inclusive: treat religion, caste, age and
gender neutrally, with no stereotypes and no pressure. Where the two differ, frame it as
something to talk about, not a warning. Don't repeat the percentages in the text; the screen
already shows them. Conversation starters must be natural questions one person could send the
other as a first message, based on something specific in the profiles."""


# ------------------------------------------------------------------ inputs
def _facts(profile) -> dict:
    prefs = _parse_pref_values(profile.pref_values)
    tags = [str(t) for t in (profile.lifestyle_tags or [])]
    return {
        "first_name": (profile.full_name or "").split(" ")[0] or "This person",
        "age": profile.age,
        "city": (profile.location or "").split(",")[0].strip() or None,
        "bio": (profile.bio or "")[:600] or None,
        "interests": sorted(interests(profile).values()),
        "lifestyle_tags": [t for t in tags if t.lower() not in {i.lower() for i in interests(profile).values()}],
        "relationship_goal": profile.relationship_goal or None,
        "religion": profile.religion or None,
        "education": profile.education or None,
        "occupation": profile.occupation or None,
        "work_preference": profile.work_preference or None,
        "languages": prefs.get("languages") or None,
    }


def _scores(result: CompatibilityResult) -> dict:
    return {
        "overall": result.compatibility_score,
        "core_values": result.values_score,
        "lifestyle_and_habits": result.lifestyle_score,
        "career_and_ambition": result.career_score,
        "hobbies_and_leisure": result.hobbies_score,
    }


def _model() -> str:
    return getattr(settings, "MATCH_INSIGHTS_MODEL", "") or "claude-opus-5"


def _api_key() -> str:
    # settings reads DuoBackend/.env, which python-decouple does not copy into os.environ.
    return getattr(settings, "ANTHROPIC_API_KEY", "") or os.environ.get("ANTHROPIC_API_KEY", "")


def _input_key(facts_a: dict, facts_b: dict, scores: dict) -> str:
    raw = json.dumps([PROMPT_VERSION, _model(), facts_a, facts_b, scores], sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def ai_enabled() -> bool:
    """True when the SDK can find credentials (API key or auth token)."""
    if getattr(settings, "MATCH_INSIGHTS_PROVIDER", "local") != "claude":
        return False
    return bool(_api_key() or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


# ------------------------------------------------------------------ generation
def _generate(facts_a: dict, facts_b: dict, scores: dict) -> AiMatchInsights | None:
    key = _api_key()
    client = anthropic.Anthropic(api_key=key, timeout=90.0, max_retries=2) if key else anthropic.Anthropic(
        timeout=90.0, max_retries=2
    )
    payload = json.dumps({"person_a": facts_a, "person_b": facts_b, "scores": scores}, indent=1, default=str)
    try:
        response = client.beta.messages.parse(
            model=_model(),
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Write the match insights for this pair.\n\n{payload}"}],
            output_format=AiMatchInsights,
            output_config={"effort": "medium"},
            # If a safety classifier declines, the API retries on a fallback model in the same call.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.AuthenticationError:
        logger.warning("match_ai_insights_auth_failed")
        return None
    except anthropic.RateLimitError:
        logger.warning("match_ai_insights_rate_limited")
        return None
    except anthropic.APIStatusError as exc:
        logger.warning("match_ai_insights_api_error status=%s", exc.status_code)
        return None
    except anthropic.APIConnectionError:
        logger.warning("match_ai_insights_connection_error")
        return None

    if response.stop_reason in ("refusal", "max_tokens"):
        logger.warning("match_ai_insights_incomplete stop_reason=%s", response.stop_reason)
        return None
    return response.parsed_output


def get_match_insights(match, *, force: bool = False) -> dict:
    """Fresh engine scores + AI text (cached on the match). Always returns a dict.

    Keys: engine fields (scores, shared_interests, spark_factors, vision/communication)
    plus ``ai_generated``, ``insight_summary``, ``pillar_notes``, ``conversation_starters``.
    """
    p1, p2 = match.user1.profile, match.user2.profile
    result = compute_compatibility(p1, p2)
    fields = result.as_match_fields()

    # Keep stored scores in step with the engine (older matches held placeholder data).
    changed = [k for k, v in fields.items() if getattr(match, k) != v]
    for k in changed:
        setattr(match, k, fields[k])

    out = {**fields, "ai_generated": False, "insight_summary": "", "pillar_notes": None,
           "conversation_starters": []}

    facts_a, facts_b, scores = _facts(p1), _facts(p2), _scores(result)
    key = _input_key(facts_a, facts_b, scores)

    cached = match.ai_insights if isinstance(match.ai_insights, dict) else None
    # "Regenerate" is rate limited per match so repeated taps can't run up API cost.
    if force and match.ai_insights_generated_at and (
        timezone.now() - match.ai_insights_generated_at
    ).total_seconds() < REFRESH_COOLDOWN_SECONDS:
        force = False
    if cached and match.ai_insights_key == key and not force:
        ai = cached
    elif ai_enabled():
        parsed = _generate(facts_a, facts_b, scores)
        ai = parsed.model_dump() if parsed else None
        if ai:
            match.ai_insights = ai
            match.ai_insights_key = key
            match.ai_insights_generated_at = timezone.now()
            changed += ["ai_insights", "ai_insights_key", "ai_insights_generated_at"]
    else:
        ai = None

    if changed:
        match.save(update_fields=sorted(set(changed)))

    if ai:
        out.update(
            ai_generated=True,
            insight_summary=ai.get("summary", ""),
            pillar_notes=ai.get("pillar_notes"),
            spark_factors=ai.get("spark_factors") or out["spark_factors"],
            shared_interests=ai.get("shared_interests") or out["shared_interests"],
            vision_insight=ai.get("vision_insight") or out["vision_insight"],
            communication_insight=ai.get("communication_insight") or out["communication_insight"],
            conversation_starters=ai.get("conversation_starters") or [],
        )
    return out
