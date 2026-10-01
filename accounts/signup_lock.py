"""Serialise account creation per email so simultaneous requests can't make duplicates."""
import time
from contextlib import contextmanager

from django.core.cache import cache

LOCK_TTL_SECONDS = 30
WAIT_SECONDS = 10


@contextmanager
def email_signup_lock(email: str):
    key = f"signup_lock:{(email or '').strip().lower()}"
    deadline = time.monotonic() + WAIT_SECONDS
    acquired = cache.add(key, "1", LOCK_TTL_SECONDS)
    while not acquired and time.monotonic() < deadline:
        time.sleep(0.1)
        acquired = cache.add(key, "1", LOCK_TTL_SECONDS)
    try:
        yield
    finally:
        if acquired:
            cache.delete(key)
