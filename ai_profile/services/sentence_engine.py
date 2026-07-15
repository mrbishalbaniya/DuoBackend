from __future__ import annotations

from ai_profile.models import SentenceTemplate
from ai_profile.services.grammar_engine import GrammarEngine
from ai_profile.services.profile_context import ProfileContext
from ai_profile.services.template_engine import TemplateEngine


# Map noisy interest tokens → template subcategory keys
INTEREST_ALIASES: dict[str, str] = {
    "gym": "gym",
    "fitness": "gym",
    "workout": "gym",
    "travel": "travel",
    "trekking": "travel",
    "hiking": "hiking",
    "music": "music",
    "movies": "movies",
    "films": "movies",
    "coding": "coding",
    "programming": "coding",
    "tech": "coding",
    "reading": "reading",
    "books": "reading",
    "cooking": "cooking",
    "photography": "photography",
    "yoga": "yoga",
    "football": "sports",
    "cricket": "sports",
    "sports": "sports",
    "dance": "dance",
    "art": "art",
    "pets": "pets",
    "dogs": "pets",
    "cats": "pets",
}


class SentenceEngine:
    """Pick modular sentence variations for profile facets."""

    def __init__(self, templates: TemplateEngine, grammar: GrammarEngine | None = None):
        self.templates = templates
        self.grammar = grammar or GrammarEngine()
        self._used: set[str] = set()

    def reset(self) -> None:
        self._used.clear()

    def _take(self, category: str, subcategory: str, *, fallbacks: list[str] | None = None) -> str | None:
        text = self.templates.pick(
            category,
            subcategory,
            fallback_subcategories=fallbacks,
            exclude_texts=self._used,
        )
        if text:
            self._used.add(text)
        return text

    def opener(self, ctx: ProfileContext, traits: list[str]) -> str | None:
        name = ctx.first_name or "Someone"
        loc = ctx.city or ctx.location or "Nepal"
        style_open = self._take(SentenceTemplate.CATEGORY_OPENER, "generic")
        filled = self.grammar.fill_placeholders(
            style_open or "",
            {"name": name, "location": loc, "occupation": ctx.occupation or "my work"},
        )
        if filled:
            return filled
        return f"I'm {name}, based in {loc}."

    def occupation_sentence(self, ctx: ProfileContext) -> str | None:
        if not ctx.occupation.strip():
            # Avoid templates that require {occupation}
            text = self._take(
                SentenceTemplate.CATEGORY_OCCUPATION,
                "no_role",
                fallbacks=[],
            )
            if text:
                return self.grammar.fill_placeholders(text, {})
            return "I care about doing meaningful work and growing in my career."

        key = self._occupation_key(ctx.occupation)
        text = self._take(SentenceTemplate.CATEGORY_OCCUPATION, key, fallbacks=["generic"])
        filled = self.grammar.fill_placeholders(
            text or "",
            {"occupation": ctx.occupation.strip()},
        )
        if filled:
            return filled
        return f"Professionally, I work as a {ctx.occupation.strip()} and care about doing meaningful work."

    def education_sentence(self, ctx: ProfileContext) -> str | None:
        if not ctx.education:
            return None
        key = self._education_key(ctx.education)
        text = self._take(SentenceTemplate.CATEGORY_EDUCATION, key, fallbacks=["generic"])
        filled = self.grammar.fill_placeholders(
            text or "",
            {"education": ctx.education.strip()},
        )
        return filled or None

    def location_sentence(self, ctx: ProfileContext) -> str | None:
        place = ctx.city or ctx.location
        if not place:
            return None
        text = self._take(SentenceTemplate.CATEGORY_LOCATION, "generic")
        filled = self.grammar.fill_placeholders(text or "", {"location": place.strip()})
        return filled or f"I currently call {place.strip()} home."

    def interest_sentences(self, ctx: ProfileContext, *, limit: int = 3) -> list[str]:
        subs: list[str] = []
        for token in ctx.interest_keys():
            mapped = INTEREST_ALIASES.get(token)
            if mapped and mapped not in subs:
                subs.append(mapped)
        if not subs:
            subs = ["generic"]
        phrases = self.templates.pick_many(
            SentenceTemplate.CATEGORY_INTEREST,
            subs,
            limit=limit,
            exclude_texts=self._used,
        )
        for phrase in phrases:
            self._used.add(phrase)
        return phrases

    def lifestyle_sentences(self, ctx: ProfileContext) -> list[str]:
        out: list[str] = []
        mapping = [
            (f"smoking:{ctx.smoking}" if ctx.smoking else "", "smoking"),
            (f"drinking:{ctx.drinking}" if ctx.drinking else "", "drinking"),
            (f"exercise:{ctx.exercise}" if ctx.exercise else "", "exercise"),
            (ctx.lifestyle, "lifestyle"),
        ]
        for value, kind in mapping:
            if not value:
                continue
            sub = value if kind in {"smoking", "drinking", "exercise"} else f"lifestyle:{value}"
            # For smoking/drinking/exercise store subcategory like smoking:never
            if kind == "lifestyle":
                sub = f"pace:{value}"
            text = self._take(SentenceTemplate.CATEGORY_LIFESTYLE, sub, fallbacks=[kind, "generic"])
            if text:
                out.append(text)
        return out

    def personality_sentences(self, traits: list[str], *, limit: int = 2) -> list[str]:
        phrases: list[str] = []
        for trait in traits:
            if len(phrases) >= limit:
                break
            text = self._take(SentenceTemplate.CATEGORY_PERSONALITY, trait, fallbacks=["generic"])
            if text:
                phrases.append(text)
        return phrases

    def value_sentence(self, ctx: ProfileContext) -> str | None:
        if ctx.relationship_goal in {"serious", "marriage"}:
            return self._take(SentenceTemplate.CATEGORY_VALUE, "serious", fallbacks=["generic"])
        if ctx.relationship_goal == "dating":
            return self._take(SentenceTemplate.CATEGORY_VALUE, "dating", fallbacks=["generic"])
        return self._take(SentenceTemplate.CATEGORY_VALUE, "generic")

    def closer(self) -> str | None:
        return self._take(SentenceTemplate.CATEGORY_CLOSER, "generic")

    def connector(self, index: int = 0) -> str | None:
        return self._take(SentenceTemplate.CATEGORY_CONNECTOR, "generic") or GrammarEngine.CONNECTOR_FALLBACKS[
            index % len(GrammarEngine.CONNECTOR_FALLBACKS)
        ]

    @staticmethod
    def _occupation_key(occupation: str) -> str:
        text = occupation.lower()
        for key in (
            "engineer",
            "developer",
            "doctor",
            "nurse",
            "teacher",
            "student",
            "designer",
            "business",
            "manager",
            "lawyer",
            "accountant",
            "artist",
        ):
            if key in text:
                return key
        return "generic"

    @staticmethod
    def _education_key(education: str) -> str:
        text = education.lower()
        if "computer" in text or "it" in text or "software" in text:
            return "computer_science"
        if "engineer" in text:
            return "engineering"
        if "medic" in text or "mbbs" in text or "health" in text:
            return "medical"
        if "business" in text or "mba" in text or "management" in text:
            return "business"
        if "law" in text:
            return "law"
        return "generic"
