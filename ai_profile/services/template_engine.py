from __future__ import annotations

import random
from functools import lru_cache

from django.db.models import Q

from ai_profile.models import SentenceTemplate


class TemplateEngine:
    """Weighted template selector backed by SentenceTemplate rows."""

    def __init__(self, *, language: str = "en", style: str = "friendly", rng: random.Random | None = None):
        self.language = language
        self.style = style
        self.rng = rng or random.Random()

    def pick(
        self,
        category: str,
        subcategory: str = "",
        *,
        fallback_subcategories: list[str] | None = None,
        exclude_texts: set[str] | None = None,
    ) -> str | None:
        candidates = self._candidates(category, subcategory)
        if not candidates and fallback_subcategories:
            for sub in fallback_subcategories:
                candidates = self._candidates(category, sub)
                if candidates:
                    break
        if not candidates:
            candidates = self._candidates(category, "generic")
        if exclude_texts:
            filtered = [row for row in candidates if row["text"] not in exclude_texts]
            if filtered:
                candidates = filtered
        if not candidates:
            return None
        weights = [max(1, int(row["weight"])) for row in candidates]
        choice = self.rng.choices(candidates, weights=weights, k=1)[0]
        return choice["text"]

    def pick_many(
        self,
        category: str,
        subcategories: list[str],
        *,
        limit: int = 3,
        exclude_texts: set[str] | None = None,
    ) -> list[str]:
        used = set(exclude_texts or set())
        phrases: list[str] = []
        for sub in subcategories:
            if len(phrases) >= limit:
                break
            text = self.pick(category, sub, exclude_texts=used)
            if not text:
                continue
            phrases.append(text)
            used.add(text)
        return phrases

    def _candidates(self, category: str, subcategory: str) -> list[dict]:
        return _load_templates(
            language=self.language,
            style=self.style,
            category=category,
            subcategory=(subcategory or "").lower().strip(),
        )


@lru_cache(maxsize=256)
def _load_templates(language: str, style: str, category: str, subcategory: str) -> tuple[dict, ...]:
    qs = SentenceTemplate.objects.filter(
        active=True,
        language=language,
        category=category,
    ).filter(Q(style=style) | Q(style="any"))
    if subcategory:
        qs = qs.filter(subcategory__iexact=subcategory)
    else:
        qs = qs.filter(subcategory="")

    rows = tuple(
        {"text": row.text.strip(), "weight": row.weight}
        for row in qs.only("text", "weight")
        if row.text and row.text.strip()
    )
    return rows


def clear_template_cache() -> None:
    _load_templates.cache_clear()
