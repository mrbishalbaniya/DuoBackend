"""Match insights from Duo's own trained model (no external AI service).

* Overall score: the model's like-probability for this pair, shown as its
  percentile among real training pairs (1-99).
* Pillar scores: the deterministic engine (easy to explain, stable).
* Spark factors / pillar notes: the features that pushed this pair's
  prediction up the most, written from real profile facts.
* Vision / communication: goals and religion, plus how the two actually chat
  (message counts and typical reply time from the conversation).
* Conversation starters: built from the other person's profile and ranked by
  learned reply rates (see ``matching.ml.starters``).
"""
from __future__ import annotations

import statistics
import time

from matching.compatibility import PERSONALITY, _one_of, compute_compatibility
from matching.ml.features import FEATURES, pair_features, shared_interests
from matching.ml.model import MatchModel
from matching.ml.starters import build_starters
from matching.recommendation.scoring import _parse_pref_values

_CACHE: dict = {"model": None, "loaded_at": 0.0, "artifact_id": None}
CACHE_SECONDS = 300


def load_model() -> tuple[MatchModel | None, dict]:
    """Active trained model (cached in-process for a few minutes)."""
    from matching.models import MatchModelArtifact

    if time.time() - _CACHE["loaded_at"] < CACHE_SECONDS:
        return _CACHE["model"], _CACHE.get("info", {})
    art = MatchModelArtifact.objects.filter(is_active=True).order_by("-created_at").first()
    model = MatchModel.from_payload(art.payload) if art else None
    info = (
        {
            "name": art.name,
            "version": art.pk,
            "trained_at": art.created_at.isoformat(),
            "samples": art.samples,
            "cv_auc": (art.metrics or {}).get("cv_auc"),
            "baseline_auc": (art.metrics or {}).get("baseline_auc"),
        }
        if art and model
        else {}
    )
    _CACHE.update(model=model, info=info, loaded_at=time.time())
    return model, info


def reset_model_cache() -> None:
    _CACHE.update(model=None, info={}, loaded_at=0.0)


def _first(p) -> str:
    return (p.full_name or "").split(" ")[0] or "They"


# ------------------------------------------------------------------ fact sentences
def _positive_fact(name: str, a, b, raw: dict, shared: list[str]) -> str | None:
    val = raw.get(name)
    if name == "hobbies" or name == "shared_count":
        if len(shared) >= 2:
            return f"You both enjoy {', '.join(shared[:3])}"
        if len(shared) == 1:
            return f"You both enjoy {shared[0]}"
        return None
    if val is None or val < 0.75:
        return None
    return {
        "goal": f"Both looking for a {a.relationship_goal or 'similar'} relationship",
        "religion": f"You share the same religion ({a.religion})" if a.religion else None,
        "caste": "Your family backgrounds line up",
        "languages": "You speak a common language",
        "smoking": "Matching views on smoking",
        "drinking": "Matching drinking habits",
        "exercise": "Similar fitness routines",
        "diet": "Similar food habits",
        "personality": "Compatible personalities",
        "age_fit": "Each of you fits the other's preferred age range",
        "distance": "You live close to each other",
        "education": "Similar level of education",
        "occupation": "You work in similar fields",
        "work": f"Both prefer {(a.work_preference or '').lower()} work".strip(),
    }.get(name)


def _gap_fact(name: str, raw: dict) -> str | None:
    val = raw.get(name)
    if val is None or val > 0.4:
        return None
    return {
        "goal": "Your relationship goals differ, so talk about expectations early",
        "religion": "You follow different religions, a good topic to understand each other",
        "smoking": "You see smoking differently",
        "drinking": "Your drinking habits differ",
        "distance": "You live a fair distance apart",
        "age_fit": "One of you is outside the other's preferred age range",
        "education": "Your education paths are quite different",
    }.get(name)


def _chat_stats(match, viewer_id: int) -> dict:
    from chat.models import Conversation, Message

    convo = Conversation.objects.filter(match=match).first()
    if not convo:
        return {}
    msgs = list(
        Message.objects.filter(conversation=convo, message_type="text")
        .order_by("timestamp")
        .values_list("sender_id", "timestamp")[:500]
    )
    if not msgs:
        return {"total": 0}
    other_id = match.user2_id if viewer_id == match.user1_id else match.user1_id
    reply_gaps = [
        (t2 - t1).total_seconds()
        for (s1, t1), (s2, t2) in zip(msgs, msgs[1:])
        if s1 == viewer_id and s2 == other_id
    ]
    return {
        "total": len(msgs),
        "mine": sum(1 for s, _ in msgs if s == viewer_id),
        "theirs": sum(1 for s, _ in msgs if s == other_id),
        "their_reply_seconds": statistics.median(reply_gaps) if reply_gaps else None,
    }


def _human_duration(seconds: float) -> str:
    if seconds < 90:
        return "about a minute"
    if seconds < 3600:
        return f"about {round(seconds / 60)} minutes"
    if seconds < 86400:
        return f"about {round(seconds / 3600)} hours"
    return f"about {round(seconds / 86400)} days"


# ------------------------------------------------------------------ main
def local_insights(match, viewer) -> dict | None:
    """Insights for ``viewer`` about their match, or None if no model is trained."""
    model, info = load_model()
    if model is None:
        return None

    me = match.user1 if viewer.id == match.user1_id else match.user2
    other = match.user2 if viewer.id == match.user1_id else match.user1
    a, b = me.profile, other.profile

    feats = pair_features(a, b)
    x = feats.vector()
    prob = model.predict_proba(x)
    contrib = model.contributions(x)
    engine = compute_compatibility(a, b)
    shared = shared_interests(a, b)

    # Rank base features by how much they raised this pair's prediction.
    base = [n for n in FEATURES]
    ranked = sorted(base, key=lambda n: -contrib.get(n, 0.0))
    sparks: list[str] = []
    for n in ranked:
        if contrib.get(n, 0.0) <= 0:
            break
        fact = _positive_fact(n, a, b, feats.raw, shared)
        if fact and fact not in sparks:
            sparks.append(fact)
        if len(sparks) == 3:
            break
    if not sparks:  # model found nothing strong: fall back to engine facts
        sparks = engine.spark_factors[:3]

    gaps = [g for n in sorted(base, key=lambda n: contrib.get(n, 0.0)) if (g := _gap_fact(n, feats.raw))][:2]

    # Pillar notes: strongest known fact per pillar, else what to add.
    notes = {}
    for pillar, missing_hint in (
        ("values", "Add your relationship goal, religion and languages to compare values."),
        ("lifestyle", "Add habits like smoking, drinking, exercise and diet to compare lifestyles."),
        ("career", "Add education and occupation to compare career paths."),
        ("hobbies", "Add a few interests to find hobbies in common."),
    ):
        names = [n for n in ranked if FEATURES[n] == pillar]
        text = next((f for n in names if (f := _positive_fact(n, a, b, feats.raw, shared))), None)
        if not text:
            text = next((g for n in names if (g := _gap_fact(n, feats.raw))), None)
        notes[pillar] = (text + ".") if text else missing_hint

    # Vision & communication from real facts.
    vision_parts = []
    if feats.raw.get("goal") == 1.0:
        vision_parts.append(f"You're both looking for a {a.relationship_goal} relationship.")
    elif feats.raw.get("goal") is not None:
        vision_parts.append("Your relationship goals aren't identical, so it's worth sharing what you each hope for.")
    fg = (_parse_pref_values(b.pref_values).get("futureGoals") or "").strip()
    if fg:
        vision_parts.append(f"{_first(b)}'s future goals: “{fg[:120]}”.")
    if gaps:
        vision_parts.append(gaps[0] + ".")
    vision = " ".join(vision_parts) or "Add relationship goals and future plans to both profiles for a vision insight."

    stats = _chat_stats(match, viewer.id)
    comm_parts = []
    if stats.get("total"):
        comm_parts.append(
            f"You've exchanged {stats['total']} messages ({stats['mine']} from you, {stats['theirs']} from {_first(b)})."
        )
        if stats.get("their_reply_seconds") is not None:
            comm_parts.append(f"{_first(b)} usually replies in {_human_duration(stats['their_reply_seconds'])}.")
    else:
        comm_parts.append("You haven't chatted yet. One of the starters below is an easy way in.")
    pers_a, pers_b = _one_of(a, PERSONALITY), _one_of(b, PERSONALITY)
    if pers_a and pers_b:
        comm_parts.append(f"You're {pers_a} and {_first(b)} is {pers_b}.")
    communication = " ".join(comm_parts)

    score = model.score_100(prob)
    lead = sparks[0].rstrip(".") if sparks else "You have room to discover what you share"
    summary = (
        f"Duo's model rates this pair higher than {score}% of pairs it has learned from. "
        f"{lead}{'.' if not lead.endswith('.') else ''}"
    )

    starters = build_starters(
        a, b, shared, model.starter_stats, seed=f"{match.id}:{viewer.id}", limit=4
    )

    return {
        "compatibility_score": score,
        "model_probability": round(prob, 4),
        "insight_summary": summary,
        "pillar_notes": notes,
        "spark_factors": sparks,
        "shared_interests": shared or engine.shared_interests,
        "vision_insight": vision,
        "communication_insight": communication,
        "conversation_starters": starters,
        "things_to_talk_about": gaps,
        "model_info": info,
    }
