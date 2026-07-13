"""Celery task package — import submodules so workers register all tasks."""

from __future__ import annotations

from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore[assignment]

_NETWORK_EXCEPTIONS: tuple[type[BaseException], ...] = (
    ConnectionError,
    TimeoutError,
    OSError,
)
if requests is not None:
    _NETWORK_EXCEPTIONS = _NETWORK_EXCEPTIONS + (requests.exceptions.RequestException,)

NETWORK_RETRY_KWARGS: dict[str, Any] = {
    "autoretry_for": _NETWORK_EXCEPTIONS,
    "retry_backoff": True,
    "retry_backoff_max": 300,
    "retry_jitter": True,
    "max_retries": 5,
}

from duo_project.tasks import email as email  # noqa: E402, F401
from duo_project.tasks import maintenance as maintenance  # noqa: E402, F401
from duo_project.tasks import monitoring as monitoring  # noqa: E402, F401
from duo_project.tasks import verification as verification  # noqa: E402, F401
