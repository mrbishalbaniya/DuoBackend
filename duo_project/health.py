from django.db import connection
from django.http import JsonResponse
from django.urls import NoReverseMatch, reverse
import os


def health_check(_request):
    """Public health endpoint for load balancers and Render."""
    db_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        db_ok = False

    wallet_routes = False
    try:
        reverse("wallet")
        reverse("wallet_topup_initiate")
        wallet_routes = True
    except NoReverseMatch:
        wallet_routes = False

    status_code = 200 if db_ok else 503
    commit = os.environ.get("RENDER_GIT_COMMIT", "")
    return JsonResponse(
        {
            "status": "ok" if db_ok else "degraded",
            "database": db_ok,
            "api_version": commit[:8] if commit else "local",
            "features": {"wallet": wallet_routes},
            "wallet_routes": wallet_routes,
        },
        status=status_code,
    )
