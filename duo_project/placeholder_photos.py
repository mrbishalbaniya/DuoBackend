"""Shared placeholder portrait URLs (Unsplash — picsum.photos often unreachable)."""

from __future__ import annotations

PLACEHOLDER_PHOTOS = [
    "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=600&h=800&fit=crop&q=80",
    "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=600&h=800&fit=crop&q=80",
    "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=600&h=800&fit=crop&q=80",
    "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=600&h=800&fit=crop&q=80",
    "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?w=600&h=800&fit=crop&q=80",
    "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=600&h=800&fit=crop&q=80",
    "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=600&h=800&fit=crop&q=80",
    "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=600&h=800&fit=crop&q=80",
]


def _hash_seed(seed: str) -> int:
    value = 0
    for char in seed:
        value = (value * 31 + ord(char)) & 0xFFFFFFFF
    return value


def placeholder_photo_url(seed: str, index: int = 0, width: int = 600, height: int = 800) -> str:
    base = PLACEHOLDER_PHOTOS[(_hash_seed(seed) + index) % len(PLACEHOLDER_PHOTOS)]
    return base.replace("w=600&h=800", f"w={width}&h={height}")


def photo_urls_for_seed(seed: str, user_id: int | None = None) -> list[str]:
    uid = user_id if user_id is not None else seed
    return [
        placeholder_photo_url(f"{seed}-1", 0),
        placeholder_photo_url(f"{seed}-2", 1),
        placeholder_photo_url(f"{uid}-3", 2),
    ]
