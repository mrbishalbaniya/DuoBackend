"""Fault-tolerant cache access with hit/miss logging."""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from typing import Any, Callable

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger("duo.cache")

_stats_lock = threading.Lock()
_stats: dict[str, int] = defaultdict(int)


class ApiCacheService:
    """Wrap Django cache with graceful degradation and lightweight metrics."""

    def _enabled(self) -> bool:
        return bool(getattr(settings, "CACHE_ENABLED", True))

    def get(self, key: str, *, label: str = "") -> Any | None:
        if not self._enabled():
            return None
        try:
            value = cache.get(key)
            if value is not None:
                self._record("hit", label)
                logger.debug("cache_hit key=%s label=%s", key, label or "-")
                return value
            self._record("miss", label)
            logger.debug("cache_miss key=%s label=%s", key, label or "-")
            return None
        except Exception as exc:
            self._record("error", label)
            logger.warning("cache_get_failed key=%s label=%s error=%s", key, label or "-", exc)
            return None

    def set(self, key: str, value: Any, ttl: int, *, label: str = "") -> bool:
        if not self._enabled():
            return False
        try:
            cache.set(key, value, ttl)
            return True
        except Exception as exc:
            self._record("error", label)
            logger.warning("cache_set_failed key=%s label=%s error=%s", key, label or "-", exc)
            return False

    def delete(self, key: str, *, label: str = "") -> None:
        if not self._enabled():
            return
        try:
            cache.delete(key)
            self._record("invalidate", label)
            logger.debug("cache_delete key=%s label=%s", key, label or "-")
        except Exception as exc:
            logger.warning("cache_delete_failed key=%s error=%s", key, exc)

    def delete_many(self, keys: list[str], *, label: str = "") -> None:
        if not self._enabled():
            return
        if not keys:
            return
        try:
            cache.delete_many(keys)
            self._record("invalidate", label, amount=len(keys))
            logger.debug("cache_delete_many count=%s label=%s", len(keys), label or "-")
        except Exception as exc:
            logger.warning("cache_delete_many_failed count=%s error=%s", len(keys), exc)

    def get_or_set(
        self,
        key: str,
        builder: Callable[[], Any],
        ttl: int,
        *,
        label: str = "",
    ) -> Any:
        cached = self.get(key, label=label)
        if cached is not None:
            return cached
        started = time.perf_counter()
        value = builder()
        elapsed_ms = (time.perf_counter() - started) * 1000
        if elapsed_ms > 250:
            logger.info("slow_cache_builder label=%s ms=%.1f key=%s", label or "-", elapsed_ms, key)
        self.set(key, value, ttl, label=label)
        return value

    def incr(self, key: str, *, label: str = "", default: int = 1) -> int:
        if not self._enabled():
            return default
        try:
            return cache.incr(key)
        except ValueError:
            cache.set(key, default + 1, None)
            return default + 1
        except Exception as exc:
            logger.warning("cache_incr_failed key=%s error=%s", key, exc)
            return default

    def get_stats(self) -> dict[str, int]:
        with _stats_lock:
            return dict(_stats)

    def _record(self, event: str, label: str, *, amount: int = 1) -> None:
        with _stats_lock:
            _stats[event] += amount
            if label:
                _stats[f"{event}:{label}"] += amount


api_cache = ApiCacheService()
