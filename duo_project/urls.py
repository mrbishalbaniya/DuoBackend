from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.permissions import AllowAny

from duo_project.admin_account import admin_account
from duo_project.health import health_check


class PublicSchemaView(SpectacularAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []


class PublicSwaggerView(SpectacularSwaggerView):
    permission_classes = [AllowAny]
    authentication_classes = []


class PublicRedocView(SpectacularRedocView):
    permission_classes = [AllowAny]
    authentication_classes = []


urlpatterns = [
    path("health/", health_check, name="health"),
    path("admin/account/", admin_account, name="admin-account"),
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/profiles/", include("accounts.profile_urls")),
    path("api/matching/", include("matching.urls")),
    path("api/chat/", include("chat.urls")),
    path("api/subscriptions/", include("subscriptions.urls")),
    path("api/wallet/", include("subscriptions.wallet_urls")),
    path("api/photos/", include("photo_verification.urls")),
    path("api/verification/", include("photo_verification.verification_urls")),
    path("api/weather/", include("weather.urls")),
    path("api/notifications/", include("notifications.urls")),
    path("api/activity/", include("activity.urls")),
    path("api/avatars/", include("avatars.urls")),
    path("api/app/", include("update.urls")),
    path("api/security/", include("security.urls")),
]

if settings.DEBUG:
    from django.conf.urls.static import static

    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path(
            "api/docs/",
            SpectacularSwaggerView.as_view(url_name="schema"),
            name="swagger-ui",
        ),
        path(
            "api/docs/redoc/",
            SpectacularRedocView.as_view(url_name="schema"),
            name="redoc",
        ),
    ]
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    urlpatterns += [
        path("api/schema/", PublicSchemaView.as_view(), name="schema"),
        path(
            "api/docs/",
            PublicSwaggerView.as_view(url_name="schema"),
            name="swagger-ui",
        ),
        path(
            "api/docs/redoc/",
            PublicRedocView.as_view(url_name="schema"),
            name="redoc",
        ),
    ]
