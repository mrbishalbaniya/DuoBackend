from datetime import timedelta
import os
from pathlib import Path

from decouple import Config, RepositoryEmpty, RepositoryEnv

BASE_DIR = Path(__file__).resolve().parent.parent
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    config = Config(RepositoryEnv(_env_file))
else:
    # Render/production: env vars come from the dashboard (Config checks os.environ first).
    config = Config(RepositoryEmpty())


def env(key: str, default=""):
    """Read from process env first, then DuoBackend/.env."""
    return os.environ.get(key) or config(key, default=default)


def _normalize_host(value: str) -> str:
    """Strip scheme/path so ALLOWED_HOSTS works when env includes a full URL."""
    value = value.strip()
    if value.startswith("https://"):
        value = value[8:]
    elif value.startswith("http://"):
        value = value[7:]
    return value.split("/")[0].strip()


def _normalize_origin(value: str) -> str:
    value = value.strip().rstrip("/")
    if not value:
        return ""
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return f"https://{value}"


def _parse_origins(value: str) -> list[str]:
    """Parse comma/newline-separated origins; ignore accidental key names pasted into values."""
    origins: list[str] = []
    for part in value.replace("\n", ",").split(","):
        origin = part.strip().rstrip("/")
        if origin.startswith("http://") or origin.startswith("https://"):
            origins.append(origin)
    return origins

SECRET_KEY = config("SECRET_KEY", default="django-insecure-duo-dev-key-change-in-production-2024")
DEBUG = config("DEBUG", default=True, cast=bool)

_INSECURE_SECRET_KEYS = {
    "",
    "change-me-in-production",
    "django-insecure-duo-dev-key-change-in-production-2024",
}
if not DEBUG:
    if SECRET_KEY in _INSECURE_SECRET_KEYS:
        raise ValueError("Set a strong SECRET_KEY environment variable for production.")
    if not env("DATABASE_URL"):
        raise ValueError("DATABASE_URL is required when DEBUG=False.")
ALLOWED_HOSTS = [
    host
    for host in (_normalize_host(part) for part in config("ALLOWED_HOSTS", default="localhost,127.0.0.1").split(","))
    if host
]

# Render/Vercel sit behind HTTPS proxies — required for admin CSRF and secure cookies.
if not DEBUG:
    USE_X_FORWARDED_HOST = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
    SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=31536000, cast=int)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "None"
    CSRF_COOKIE_SAMESITE = "None"

INSTALLED_APPS = [
    "daphne",
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "channels",
    "rest_framework",
    "rest_framework_simplejwt",
    "drf_spectacular",
    "corsheaders",
    "site_config",
    "email_service",
    "accounts",
    "matching",
    "chat",
    "subscriptions",
    "photo_verification",
    "weather",
    "notifications",
    "activity",
    "avatars",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    *(
        ["whitenoise.middleware.WhiteNoiseMiddleware"]
        if not DEBUG
        else []
    ),
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "duo_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "duo_project.wsgi.application"
ASGI_APPLICATION = "duo_project.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

_redis_url = env("REDIS_URL")
if _redis_url:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [_redis_url]},
        }
    }

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "OPTIONS": {
            # Wait up to 20s for write locks (rapid swipes + photo analysis).
            "timeout": 20,
        },
    }
}

_database_url = env("DATABASE_URL")
if _database_url:
    import dj_database_url

    _db_scheme = _database_url.split("://", 1)[0].lower()
    _db_requires_ssl = not DEBUG and _db_scheme in {"postgres", "postgresql"}

    DATABASES["default"] = dj_database_url.parse(
        _database_url,
        conn_max_age=600,
        ssl_require=_db_requires_ssl,
    )


def _configure_sqlite(sender, connection, **kwargs):
    if connection.vendor != "sqlite":
        return
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA busy_timeout=20000;")


from django.db.backends.signals import connection_created  # noqa: E402

connection_created.connect(_configure_sqlite)

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kathmandu"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# User uploads are stored in Cloudinary — not DuoBackend/media/
CLOUDINARY_CLOUD_NAME = env("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = env("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = env("CLOUDINARY_API_SECRET")
CLOUDINARY_UPLOAD_PRESET = env("CLOUDINARY_UPLOAD_PRESET")
CLOUDINARY_PROFILE_FOLDER = config("CLOUDINARY_PROFILE_FOLDER", default="duo/profile_photos")
CLOUDINARY_CHAT_FOLDER = config("CLOUDINARY_CHAT_FOLDER", default="duo/chat_media")
CLOUDINARY_VERIFICATION_FOLDER = config(
    "CLOUDINARY_VERIFICATION_FOLDER", default="duo/verification_selfies"
)

# OpenWeather — server-side only; never expose to the client
OPENWEATHER_API_KEY = env("OPENWEATHER_API_KEY")

# Firebase Cloud Messaging — admin DB values override these env defaults
FCM_ENABLED = config("FCM_ENABLED", default=False, cast=bool)
FIREBASE_PROJECT_ID = env("FIREBASE_PROJECT_ID")
FIREBASE_API_KEY = env("FIREBASE_API_KEY")
FIREBASE_AUTH_DOMAIN = env("FIREBASE_AUTH_DOMAIN")
FIREBASE_MESSAGING_SENDER_ID = env("FIREBASE_MESSAGING_SENDER_ID")
FIREBASE_APP_ID = env("FIREBASE_APP_ID")
FCM_VAPID_KEY = env("FCM_VAPID_KEY")
FIREBASE_SERVICE_ACCOUNT_JSON = env("FIREBASE_SERVICE_ACCOUNT_JSON")

# Photo verification / AI analysis
PHOTO_VERIFICATION_STRICT_REJECT = config("PHOTO_VERIFICATION_STRICT_REJECT", default=True, cast=bool)
PHOTO_AI_MODEL_PATH = env("PHOTO_AI_MODEL_PATH")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = _parse_origins(
    config(
        "CORS_ALLOWED_ORIGINS",
        default="http://localhost:3000,http://localhost:3001,http://localhost:8081,http://localhost:8082",
    )
)
CORS_ALLOW_CREDENTIALS = True

FRONTEND_URL = _normalize_origin(config("FRONTEND_URL", default="http://localhost:3000"))

_csrf_trusted = {
    _normalize_origin(origin)
    for origin in config("CSRF_TRUSTED_ORIGINS", default="").split(",")
    if origin.strip()
}
for host in ALLOWED_HOSTS:
    if host in ("localhost", "127.0.0.1"):
        _csrf_trusted.add(f"http://{host}:8000")
        _csrf_trusted.add(f"http://{host}:8001")
        _csrf_trusted.add(f"http://{host}:3000")
    else:
        _csrf_trusted.add(f"https://{host}")
if FRONTEND_URL:
    _csrf_trusted.add(FRONTEND_URL)
for origin in CORS_ALLOWED_ORIGINS:
    normalized = _normalize_origin(origin)
    if normalized:
        _csrf_trusted.add(normalized)
CSRF_TRUSTED_ORIGINS = sorted(_csrf_trusted)

GOOGLE_OAUTH_CLIENT_ID = config("GOOGLE_OAUTH_CLIENT_ID", default="")
GOOGLE_OAUTH_CLIENT_SECRET = config("GOOGLE_OAUTH_CLIENT_SECRET", default="")
GOOGLE_OAUTH_REDIRECT_URI = config(
    "GOOGLE_OAUTH_REDIRECT_URI",
    default="http://localhost:8000/api/auth/google/callback/",
)

SUBSCRIPTION_PLAN_ID = config("SUBSCRIPTION_PLAN_ID", default="duo_premium_monthly")
SUBSCRIPTION_PLAN_NAME = config("SUBSCRIPTION_PLAN_NAME", default="Duo Premium")
SUBSCRIPTION_PLAN_DESCRIPTION = config(
    "SUBSCRIPTION_PLAN_DESCRIPTION",
    default="See who liked you and unlock blurred profiles on Discover.",
)
ESEWA_PRODUCT_CODE = env("ESEWA_PRODUCT_CODE", default="EPAYTEST" if DEBUG else "").strip()
ESEWA_SECRET_KEY = env("ESEWA_SECRET_KEY", default="8gBm/:&EnhH.1/q" if DEBUG else "").strip()
ESEWA_FORM_URL = config(
    "ESEWA_FORM_URL",
    default="https://rc-epay.esewa.com.np/api/epay/main/v2/form",
)
ESEWA_STATUS_URL = config(
    "ESEWA_STATUS_URL",
    default="https://rc.esewa.com.np/api/epay/transaction/status/",
)
_render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
_backend_public_url = (
    f"https://{_render_host}".rstrip("/")
    if _render_host
    else config("BACKEND_PUBLIC_URL", default="https://duobackend.onrender.com").rstrip("/")
)
BACKEND_PUBLIC_URL = _backend_public_url
ESEWA_SUCCESS_URL = config(
    "ESEWA_SUCCESS_URL",
    default=f"{_backend_public_url}/api/subscriptions/esewa/success/",
)
ESEWA_FAILURE_URL = config(
    "ESEWA_FAILURE_URL",
    default=f"{_backend_public_url}/api/subscriptions/esewa/failure/",
)

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="smtp-relay.brevo.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_USE_SSL = config("EMAIL_USE_SSL", default=False, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="").strip()
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="").replace(" ", "")
EMAIL_DELIVERY = config("EMAIL_DELIVERY", default="smtp")
EMAIL_FROM_NAME = config("EMAIL_FROM_NAME", default="SajiloWork")
EMAIL_BRAND_LOGO_URL = config("EMAIL_BRAND_LOGO_URL", default="")
EMAIL_BRAND_PRIMARY_COLOR = config("EMAIL_BRAND_PRIMARY_COLOR", default="#6366f1")
EMAIL_FOOTER_TEXT = config("EMAIL_FOOTER_TEXT", default="© SajiloWork. All rights reserved.")
EMAIL_SOCIAL_LINKS = config("EMAIL_SOCIAL_LINKS", default="")
EMAIL_SMTP_TIMEOUT = config("EMAIL_SMTP_TIMEOUT", default=15, cast=int)
RESEND_API_KEY = config("RESEND_API_KEY", default="").strip()
BREVO_API_KEY = config("BREVO_API_KEY", default="").strip()
DEFAULT_FROM_EMAIL = config(
    "DEFAULT_FROM_EMAIL",
    default=f"SajiloWork <{EMAIL_HOST_USER}>" if EMAIL_HOST_USER else "noreply@sajilowork.com",
)

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}
if _redis_url:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": _redis_url,
        }
    }

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "accounts.authentication.CookieJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/minute",
        "user": "300/minute",
        "auth": "10/minute",
        "weather": "120/minute",
    },
    "EXCEPTION_HANDLER": "duo_project.exceptions.custom_exception_handler",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Duo API",
    "DESCRIPTION": (
        "REST API for the Duo matrimonial and dating platform. "
        "Authenticate with JWT (`Bearer <access_token>`) for protected routes. "
        "Obtain tokens via `/api/auth/login/`, `/api/auth/google/`, or `/api/auth/register/`."
    ),
    "VERSION": "1.0.0",
    "CONTACT": {"name": "Duo Team", "email": "support@duo.app"},
    "LICENSE": {"name": "Proprietary"},
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/",
    "POSTPROCESSING_HOOKS": ["duo_project.schema.postprocess_tag_groups"],
    "TAGS": [
        {"name": "Authentication", "description": "Register, login, OAuth, and OTP verification."},
        {"name": "Profiles", "description": "User profile management and photo uploads."},
        {"name": "Discovery", "description": "Browse profiles to swipe on."},
        {"name": "Matching", "description": "Swipes, matches, and compatibility insights."},
        {"name": "Chat", "description": "Conversations, messages, and media uploads."},
        {"name": "Subscriptions", "description": "Duo Premium plans and eSewa payments."},
        {"name": "Photos", "description": "AI profile photo verification and quality analysis."},
        {"name": "Verification", "description": "Selfie liveness and face-matching verification."},
        {"name": "Weather", "description": "Live OpenWeather proxy — forecasts, tiles, air quality."},
    ],
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "filter": True,
        "tryItOutEnabled": True,
        "docExpansion": "list",
        "defaultModelsExpandDepth": 2,
        "syntaxHighlight.theme": "monokai",
    },
    "REDOC_UI_SETTINGS": {
        "hideDownloadButton": False,
        "expandResponses": "200,201",
        "pathInMiddlePanel": True,
    },
    "APPEND_COMPONENTS": {
        "securitySchemes": {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "JWT access token from login, register, or Google auth.",
            }
        }
    },
    "SECURITY": [{"BearerAuth": []}],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
}

GOOGLE_OAUTH_ALLOWED_REDIRECT_URIS = [
    uri.strip().rstrip("/")
    for uri in config(
        "GOOGLE_OAUTH_ALLOWED_REDIRECT_URIS",
        default=config("GOOGLE_OAUTH_REDIRECT_URI", default="http://localhost:8000/api/auth/google/callback/"),
    ).split(",")
    if uri.strip()
]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO" if not DEBUG else "DEBUG",
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

JAZZMIN_SETTINGS = {
    "site_title": "Duo Admin",
    "site_header": "Duo",
    "site_brand": "Duo Matrimonial",
    "site_logo": None,
    "login_logo": None,
    "welcome_sign": "Welcome to Duo Administrative Portal",
    "copyright": "Duo Matrimonial",
    "search_model": "auth.User",
    "user_avatar": None,
    "topmenu_links": [
        {
            "name": "Home",
            "url": "admin:index",
            "permissions": ["auth.view_user"],
        },
        {
            "name": "My account",
            "url": "admin-account",
            "icon": "fas fa-user-circle",
            "permissions": ["auth.view_user"],
        },
        {
            "name": "API Docs",
            "url": "/api/docs/",
            "new_window": True,
            "permissions": ["auth.view_user"],
        },
        {"model": "site_config.SiteSettings"},
        {"model": "accounts.Profile"},
    ],
    "usermenu_links": [
        {
            "name": "My account",
            "url": "admin-account",
            "icon": "fas fa-user-circle",
        },
        {
            "name": "Change password",
            "url": "admin:password_change",
            "icon": "fas fa-key",
        },
        {"model": "auth.user"},
    ],
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "accounts.Profile": "fas fa-id-card",
        "matching.Swipe": "fas fa-heart",
        "matching.Match": "fas fa-fire",
        "chat.Conversation": "fas fa-comments",
        "chat.Message": "fas fa-envelope",
        "subscriptions.SubscriptionPayment": "fas fa-crown",
        "site_config.SiteSettings": "fas fa-sliders-h",
        "email_service.EmailLog": "fas fa-paper-plane",
        "email_service.EmailTemplate": "fas fa-file-alt",
        "email_service.EmailEventSetting": "fas fa-toggle-on",
    },
    "order_with_respect_to": [
        "site_config",
        "email_service",
        "accounts",
        "matching",
        "chat",
        "subscriptions",
        "auth",
    ],
    "colorscale": "indigo",
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-primary",
    "accent": "accent-primary",
    "navbar": "navbar-light",
    "no_navbar_border": False,
    "navbar_fixed": True,
    "layout_fixed": True,
    "footer_fixed": False,
    "sidebar_fixed": False,
    "sidebar": "sidebar-dark-primary",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": False,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "flatly",
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}

_sentry_dsn = env("SENTRY_DSN")
if _sentry_dsn and not DEBUG:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=_sentry_dsn,
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
        environment="production",
    )
