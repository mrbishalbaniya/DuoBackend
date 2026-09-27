"""Like quota: free users get a fixed number of Likes per rolling window.

Every successful Like (LIKE or SUPERLIKE on someone not already liked) writes a
``LikeEvent``. The quota counts events inside the window, so a Like keeps
counting even if it is later rewound or withdrawn: otherwise like, rewind,
like again would sidestep the limit. Left swipes are never limited, and an
active "Unlimited likes" pass removes the limit entirely.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from subscriptions.services import FEATURE_UNLIMITED_LIKES, user_has_active_subscription

from .models import LikeEvent

LIKE_ACTIONS = ("LIKE", "SUPERLIKE")


def like_limit() -> int:
    return int(getattr(settings, "FREE_LIKES_PER_WINDOW", 100))


def like_window() -> timedelta:
    return timedelta(hours=int(getattr(settings, "FREE_LIKES_WINDOW_HOURS", 12)))


@dataclass(frozen=True)
class LikeQuota:
    unlimited: bool
    limit: int
    used: int
    remaining: int | None
    reset_at: datetime | None
    window_hours: int

    @property
    def exhausted(self) -> bool:
        return not self.unlimited and (self.remaining or 0) <= 0

    def as_dict(self) -> dict:
        return {
            "unlimited": self.unlimited,
            "limit": None if self.unlimited else self.limit,
            "used": self.used,
            "likes_remaining": self.remaining,
            "reset_at": self.reset_at.isoformat() if self.reset_at else None,
            "window_hours": self.window_hours,
        }


def get_like_quota(user, *, now: datetime | None = None) -> LikeQuota:
    """Current quota. ``reset_at`` is when the oldest counted Like expires,
    i.e. the moment at least one more Like becomes available."""
    now = now or timezone.now()
    window = like_window()
    window_hours = int(window.total_seconds() // 3600)
    unlimited = user_has_active_subscription(user, FEATURE_UNLIMITED_LIKES)

    recent = LikeEvent.objects.filter(user=user, created_at__gt=now - window)
    used = recent.count()

    if unlimited:
        return LikeQuota(True, like_limit(), used, None, None, window_hours)

    limit = like_limit()
    oldest = recent.order_by("created_at").values_list("created_at", flat=True).first()
    return LikeQuota(
        unlimited=False,
        limit=limit,
        used=used,
        remaining=max(0, limit - used),
        reset_at=oldest + window if oldest else None,
        window_hours=window_hours,
    )


def record_like(user, target) -> None:
    LikeEvent.objects.create(user=user, target=target)


def prune_like_events(older_than: timedelta | None = None) -> int:
    """Delete events that can no longer affect any quota."""
    cutoff = timezone.now() - (older_than or like_window() * 2)
    deleted, _ = LikeEvent.objects.filter(created_at__lt=cutoff).delete()
    return deleted
