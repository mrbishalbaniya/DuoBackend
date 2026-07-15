from __future__ import annotations

from ai_profile.models import SentenceTemplate
from ai_profile.services.grammar_engine import GrammarEngine
from ai_profile.services.profile_context import ProfileContext
from ai_profile.services.template_engine import TemplateEngine


class LookingForEngine:
    """Compose partner-preference narrative without LLMs."""

    def __init__(self, templates: TemplateEngine, grammar: GrammarEngine | None = None):
        self.templates = templates
        self.grammar = grammar or GrammarEngine()

    def generate(self, ctx: ProfileContext, traits: list[str]) -> str:
        used: set[str] = set()
        parts: list[str] = []

        def take(sub: str, *, replacements: dict[str, str] | None = None, fallbacks: list[str] | None = None) -> None:
            text = self.templates.pick(
                SentenceTemplate.CATEGORY_LOOKING,
                sub,
                fallback_subcategories=fallbacks if fallbacks is not None else ["generic"],
                exclude_texts=used,
            )
            if not text:
                return
            filled = self.grammar.fill_placeholders(text, replacements or {})
            if not filled:
                return
            used.add(text)
            parts.append(self.grammar.clean_sentence(filled))

        goal = ctx.pref_relationship_goal or ctx.relationship_goal or "serious"
        take(f"goal:{goal}")

        if ctx.pref_age_min and ctx.pref_age_max:
            take(
                "age_range",
                replacements={
                    "age_min": str(ctx.pref_age_min),
                    "age_max": str(ctx.pref_age_max),
                },
                fallbacks=[],
            )

        if ctx.pref_religion:
            take("religion", replacements={"religion": ctx.pref_religion.title()}, fallbacks=[])
        elif ctx.religion:
            take("values", fallbacks=[])

        if "active" in traits:
            take("lifestyle_active", fallbacks=[])
        if "intellectual" in traits or "analytical" in traits:
            take("lifestyle_intellectual", fallbacks=[])
        if "adventurous" in traits:
            take("lifestyle_adventurous", fallbacks=[])

        take("communication", fallbacks=[])
        take("generic", fallbacks=[])

        paragraph = self.grammar.join_paragraph(parts, target_min=40, target_max=75)
        return self.grammar.ensure_word_range(
            paragraph,
            minimum=40,
            maximum=75,
            pad_sentences=[
                "I appreciate honesty, humor, and someone who shows up with kindness.",
                "I'm hoping to meet someone kind, grounded, and ready for real partnership.",
            ],
        )
