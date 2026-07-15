from __future__ import annotations

from ai_profile.models import SentenceTemplate
from ai_profile.services.grammar_engine import GrammarEngine
from ai_profile.services.profile_context import ProfileContext
from ai_profile.services.template_engine import TemplateEngine


class FutureGoalEngine:
    """Compose a short future-goals paragraph from career/family/travel templates."""

    def __init__(self, templates: TemplateEngine, grammar: GrammarEngine | None = None):
        self.templates = templates
        self.grammar = grammar or GrammarEngine()

    def generate(self, ctx: ProfileContext, traits: list[str]) -> str:
        used: set[str] = set()
        parts: list[str] = []

        def take(sub: str) -> None:
            text = self.templates.pick(
                SentenceTemplate.CATEGORY_FUTURE,
                sub,
                fallback_subcategories=["generic"],
                exclude_texts=used,
            )
            if text:
                used.add(text)
                parts.append(self.grammar.clean_sentence(text))

        take("career")
        if "ambitious" in traits or "analytical" in traits:
            take("education")
        if ctx.relationship_goal in {"serious", "marriage"} or "caring" in traits or "family_oriented" in traits:
            take("family")
            take("marriage")
        if "adventurous" in traits or any(t in ctx.interest_keys() for t in ("travel", "hiking")):
            take("travel")
        if "active" in traits:
            take("health")
        take("financial")

        if len(parts) < 2:
            take("generic")

        paragraph = self.grammar.join_paragraph(parts, target_min=40, target_max=80)
        return self.grammar.ensure_word_range(
            paragraph,
            minimum=40,
            maximum=80,
            pad_sentences=[
                self.templates.pick(SentenceTemplate.CATEGORY_FUTURE, "generic") or "I'm excited to keep growing.",
            ],
        )
