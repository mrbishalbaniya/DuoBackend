"""Security audit logging."""

from __future__ import annotations

import logging

logger = logging.getLogger("duo.security")


def log_security_event(event: str, **context) -> None:
    safe = {k: v for k, v in context.items() if v is not None}
    logger.info("security_event=%s %s", event, " ".join(f"{k}={v}" for k, v in safe.items()))
