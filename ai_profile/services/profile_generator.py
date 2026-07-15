from __future__ import annotations

import random
import re
from dataclasses import dataclass
from django.db import transaction
from django.utils import timezone as dj_timezone

from ai_profile.models import GeneratedProfileContent
from ai_profile.services.future_goal_engine import FutureGoalEngine
from ai_profile.services.grammar_engine import GrammarEngine
from ai_profile.services.looking_for_engine import LookingForEngine
from ai_profile.services.personality_engine import PersonalityEngine
from ai_profile.services.profile_context import ProfileContext
from ai_profile.services.sentence_engine import SentenceEngine
from ai_profile.services.template_engine import TemplateEngine, clear_template_cache

GENERATION_VERSION = 2

VALID_STYLES = {
    "professional",
    "romantic",
    "funny",
    "minimal",
    "confident",
    "adventurous",
    "intellectual",
    "friendly",
}


@dataclass
class GenerationResult:
    bio: str
    future_goals: str
    looking_for: str
    traits: list[str]
    style: str
    language: str
    cached: bool
    fingerprint: str
    generation_version: int


class ProfileGenerator:
    """Fully offline profile copy generator (no third-party AI)."""

    def __init__(self, *, language: str = "en", style: str = "friendly", seed: int | None = None):
        self.language = (language or "en").lower()
        style_key = (style or "friendly").lower()
        self.style = style_key if style_key in VALID_STYLES else "friendly"
        self.rng = random.Random(seed)

    def generate_for_profile(
        self,
        profile,
        *,
        force: bool = False,
        persist: bool = True,
    ) -> GenerationResult:
        ctx = ProfileContext.from_profile(profile)
        fingerprint = ctx.fingerprint()

        cached = None
        if persist:
            cached = GeneratedProfileContent.objects.filter(user_id=profile.user_id).first()
            if (
                not force
                and cached
                and cached.source_fingerprint == fingerprint
                and cached.generation_version == GENERATION_VERSION
                and cached.language == self.language
                and cached.style == self.style
                and cached.generated_bio
                and cached.generated_future_goals
                and cached.generated_looking_for
            ):
                return GenerationResult(
                    bio=cached.generated_bio,
                    future_goals=cached.generated_future_goals,
                    looking_for=cached.generated_looking_for,
                    traits=list(cached.traits or []),
                    style=cached.style,
                    language=cached.language,
                    cached=True,
                    fingerprint=cached.source_fingerprint,
                    generation_version=cached.generation_version,
                )

        result = self._compose(ctx)

        if persist:
            with transaction.atomic():
                obj, _ = GeneratedProfileContent.objects.update_or_create(
                    user_id=profile.user_id,
                    defaults={
                        "generated_bio": result.bio,
                        "generated_future_goals": result.future_goals,
                        "generated_looking_for": result.looking_for,
                        "style": self.style,
                        "language": self.language,
                        "traits": result.traits,
                        "source_fingerprint": fingerprint,
                        "generation_version": GENERATION_VERSION,
                        "generated_at": dj_timezone.now(),
                    },
                )
                result.fingerprint = obj.source_fingerprint

        result.cached = False
        return result

    def _compose(self, ctx: ProfileContext) -> GenerationResult:
        templates = TemplateEngine(language=self.language, style=self.style, rng=self.rng)
        grammar = GrammarEngine()
        personality = PersonalityEngine()
        sentences = SentenceEngine(templates, grammar)
        future_engine = FutureGoalEngine(templates, grammar)
        looking_engine = LookingForEngine(templates, grammar)

        traits = personality.infer(ctx)
        sentences.reset()

        blocks: list[str] = []

        opener = sentences.opener(ctx, traits)
        if opener:
            blocks.append(grammar.clean_sentence(opener))

        for raw in (
            sentences.occupation_sentence(ctx),
            sentences.education_sentence(ctx),
            sentences.location_sentence(ctx),
        ):
            if raw:
                blocks.append(grammar.clean_sentence(raw))

        for idx, phrase in enumerate(sentences.interest_sentences(ctx, limit=3)):
            connector = sentences.connector(idx)
            blocks.append(grammar.with_connector(connector, phrase, index=idx))

        for phrase in sentences.lifestyle_sentences(ctx)[:2]:
            blocks.append(grammar.clean_sentence(phrase))

        for phrase in sentences.personality_sentences(traits, limit=2):
            blocks.append(grammar.clean_sentence(phrase))

        value = sentences.value_sentence(ctx)
        if value:
            blocks.append(grammar.clean_sentence(value))

        closer = sentences.closer()
        if closer:
            blocks.append(grammar.clean_sentence(closer))

        # Style shaping
        if self.style == "minimal":
            blocks = blocks[:4]
        elif self.style == "funny" and len(blocks) > 2:
            joke = templates.pick("opener", "funny") or templates.pick("closer", "funny")
            if joke:
                blocks.insert(1, grammar.clean_sentence(joke))

        bio = grammar.join_paragraph(blocks, target_min=60, target_max=95)
        bio = grammar.ensure_word_range(
            bio,
            minimum=55,
            maximum=95,
            pad_sentences=[
                templates.pick("value", "generic") or "I value honesty, kindness, and good conversation.",
                templates.pick("closer", "generic") or "I'd love to meet someone genuine.",
            ],
        )
        bio = grammar.hard_char_limit(bio, 500)
        # Final safety: never ship unresolved template tokens
        bio = re.sub(r"\{[a-zA-Z0-9_]+\}", "", bio)
        bio = re.sub(r"\s{2,}", " ", bio).strip()

        future_goals = future_engine.generate(ctx, traits)
        looking_for = looking_engine.generate(ctx, traits)
        future_goals = grammar.hard_char_limit(future_goals, 400)
        looking_for = grammar.hard_char_limit(looking_for, 400)

        return GenerationResult(
            bio=bio,
            future_goals=future_goals,
            looking_for=looking_for,
            traits=traits,
            style=self.style,
            language=self.language,
            cached=False,
            fingerprint=ctx.fingerprint(),
            generation_version=GENERATION_VERSION,
        )


def invalidate_template_cache() -> None:
    clear_template_cache()
