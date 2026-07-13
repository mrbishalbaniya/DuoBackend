"""Static lookup tables cached for 24 hours."""

from __future__ import annotations

from accounts.models import Profile
from duo_project.cache.keys import static_lookups as static_lookups_key
from duo_project.cache.ttl import STATIC_LOOKUPS
from duo_project.cache.service import api_cache


def _choices_to_list(choices) -> list[dict[str, str]]:
    return [{"value": value, "label": str(label)} for value, label in choices]


def build_static_lookups() -> dict:
    return {
        "genders": _choices_to_list(Profile.GENDER_CHOICES),
        "religions": _choices_to_list(Profile.RELIGION_CHOICES),
        "work_preferences": _choices_to_list(Profile.WORK_PREF_CHOICES),
        "gender_preferences": _choices_to_list(Profile.GENDER_PREF_CHOICES),
        "relationship_goals": _choices_to_list(Profile.RELATIONSHIP_GOAL_CHOICES),
        "relationship_goal_preferences": _choices_to_list(
            Profile.RELATIONSHIP_GOAL_PREF_CHOICES
        ),
        "location_visibility": _choices_to_list(Profile.LOCATION_VISIBILITY_CHOICES),
    }


def get_static_lookups() -> dict:
    return api_cache.get_or_set(
        static_lookups_key(),
        build_static_lookups,
        STATIC_LOOKUPS,
        label="static_lookups",
    )
