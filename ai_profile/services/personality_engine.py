from __future__ import annotations

from ai_profile.services.profile_context import ProfileContext

# Interest / hobby keywords → personality traits
TRAIT_RULES: list[tuple[set[str], str]] = [
    ({"gym", "fitness", "hiking", "running", "yoga", "sports", "football", "cricket"}, "active"),
    ({"reading", "coding", "programming", "tech", "science", "chess"}, "analytical"),
    ({"travel", "photography", "adventure", "trekking", "exploring"}, "adventurous"),
    ({"pets", "dogs", "cats", "family", "kids", "children"}, "caring"),
    ({"business", "startup", "leadership", "entrepreneur", "finance"}, "ambitious"),
    ({"music", "movies", "film", "art", "painting", "dance", "writing"}, "creative"),
    ({"cooking", "baking", "food"}, "family_oriented"),
    ({"meditation", "spiritual", "mindfulness"}, "grounded"),
    ({"volunteering", "community", "social_work"}, "compassionate"),
]


class PersonalityEngine:
    """Infer lightweight personality traits from interests and lifestyle."""

    def infer(self, ctx: ProfileContext) -> list[str]:
        bag = set(ctx.interest_keys())
        if ctx.personality:
            bag.add(ctx.personality.lower())
        if ctx.lifestyle:
            bag.add(ctx.lifestyle.lower())
        if ctx.exercise in {"daily", "often", "regular"}:
            bag.update({"gym", "fitness"})

        traits: list[str] = []
        for keywords, trait in TRAIT_RULES:
            if bag & keywords:
                traits.append(trait)

        if len(ctx.interests) > 6 and "curious" not in traits:
            traits.append("curious")
        if ctx.occupation and any(k in ctx.occupation.lower() for k in ("engineer", "developer", "analyst")):
            if "analytical" not in traits:
                traits.append("analytical")
        if ctx.relationship_goal in {"serious", "marriage"} and "caring" not in traits:
            traits.append("caring")

        # unique preserve order
        seen: set[str] = set()
        out: list[str] = []
        for trait in traits:
            if trait in seen:
                continue
            seen.add(trait)
            out.append(trait)
        if not out:
            out.append("friendly")
        return out[:5]
