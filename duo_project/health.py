from django.db import connection
from django.http import JsonResponse
from django.urls import NoReverseMatch, reverse
import os


def _update_service_ready() -> bool:
    try:
        from update.services.bootstrap import update_table_exists

        return update_table_exists()
    except Exception:
        return False


def _cache_ping() -> bool:
    try:
        from django.core.cache import cache

        key = "duo:health:ping"
        cache.set(key, "1", 5)
        return cache.get(key) == "1"
    except Exception:
        return False


def _auth_tables_ready() -> bool:
    try:
        tables = set(connection.introspection.table_names())
        return "token_blacklist_outstandingtoken" in tables
    except Exception:
        return False


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

    update_ready = _update_service_ready() if db_ok else False
    cache_ok = _cache_ping() if db_ok else False
    auth_ready = _auth_tables_ready() if db_ok else False

    try:
        from duo_project.cache.health import cache_health

        cache_info = cache_health()
    except Exception:
        cache_info = {"backend": "unknown", "redis_configured": False}

    cache_info["ping_ok"] = cache_ok

    status_code = 200 if db_ok else 503
    commit = os.environ.get("RENDER_GIT_COMMIT", "")
    return JsonResponse(
        {
            "status": "ok" if db_ok else "degraded",
            "database": db_ok,
            "cache": cache_info,
            "auth_ready": auth_ready,
            "api_version": commit[:8] if commit else "local",
            "features": {
                "wallet": wallet_routes,
                "update_service": update_ready,
            },
            "wallet_routes": wallet_routes,
            "update_service_ready": update_ready,
        },
        status=status_code,
    )
