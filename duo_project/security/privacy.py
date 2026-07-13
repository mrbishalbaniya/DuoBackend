"""Privacy helpers — blocks, visibility."""

from __future__ import annotations

from django.db.models import Q

from chat.models import UserBlock
from matching.models import Match


def blocked_user_ids(user_id: int) -> set[int]:
    """Users blocked by or blocking this user."""
    rows = UserBlock.objects.filter(Q(blocker_id=user_id) | Q(blocked_id=user_id)).values_list(
        "blocker_id", "blocked_id"
    )
    blocked: set[int] = set()
    for blocker_id, blocked_id in rows:
        if blocker_id == user_id:
            blocked.add(blocked_id)
        else:
            blocked.add(blocker_id)
    return blocked


def users_can_see_presence(viewer_id: int, target_id: int) -> bool:
    if viewer_id == target_id:
        return True
    return Match.objects.filter(
        Q(user1_id=viewer_id, user2_id=target_id) | Q(user1_id=target_id, user2_id=viewer_id)
    ).exists()
