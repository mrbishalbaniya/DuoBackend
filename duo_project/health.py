from django.db import connection
from django.http import JsonResponse
import os


def health_check(_request):
    """Public health endpoint for load balancers and Render."""
    db_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        db_ok = False

    status_code = 200 if db_ok else 503
    commit = os.environ.get("RENDER_GIT_COMMIT", "")
    return JsonResponse(
        {
            "status": "ok" if db_ok else "degraded",
            "database": db_ok,
            "api_version": commit[:8] if commit else "local",
            "features": {"wallet": True},
        },
        status=status_code,
    )
