"""Consistent API error shape.

Every error response keeps DRF's ``detail`` (existing clients read it) and adds:
  - ``code``: stable machine-readable code the frontend switches on
  - ``message``: human-readable text safe to show users
  - ``retry_after``: seconds until retry is allowed (rate-limit errors only)
"""

import math

from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import Throttled
from rest_framework.response import Response
from rest_framework.views import exception_handler


def _format_wait(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    minutes = math.ceil(seconds / 60)
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    hours = math.ceil(minutes / 60)
    return f"{hours} hour{'s' if hours != 1 else ''}"


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        if isinstance(exc, Throttled):
            wait = max(1, math.ceil(exc.wait or 1))
            message = f"Too many requests. Please try again in {_format_wait(wait)}."
            response.data = {
                "code": "rate_limited",
                "message": message,
                "detail": message,
                "retry_after": wait,
            }
            response["Retry-After"] = str(wait)
        elif isinstance(response.data, dict) and "code" not in response.data:
            detail = response.data.get("detail")
            code = getattr(detail, "code", None) or getattr(exc, "default_code", "error")
            response.data["code"] = str(code)
            if isinstance(detail, str):
                response.data.setdefault("message", str(detail))
        return response

    if settings.DEBUG:
        return None

    return Response(
        {
            "code": "server_error",
            "message": "An unexpected error occurred. Please try again later.",
            "detail": "An unexpected error occurred. Please try again later.",
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
