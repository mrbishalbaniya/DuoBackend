"""Serializer context helpers for matching list endpoints."""

from __future__ import annotations

from accounts.serializer_context import profile_list_serializer_context


def matching_list_context(request, profiles, **extra) -> dict:
    context = profile_list_serializer_context(request, profiles)
    context.update(extra)
    return context


def profiles_from_swipes(swipes, viewer):
    profiles = []
    for swipe in swipes:
        other_user = swipe.to_user if swipe.from_user_id == viewer.id else swipe.from_user
        profiles.append(other_user.profile)
    return profiles


def profiles_from_visits(visits):
    return [visit.viewer.profile for visit in visits]
