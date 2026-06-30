"""Runtime integration settings: admin DB values override django.conf.settings env defaults."""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache

CACHE_KEY = "site_config:integration:v1"
CACHE_TTL_SECONDS = 300


@dataclass(frozen=True)
class IntegrationSettings:
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    google_allowed_redirect_uris: tuple[str, ...]
    email_host: str
    email_port: int
    email_use_tls: bool
    email_host_user: str
    email_host_password: str
    email_delivery: str
    resend_api_key: str
    default_from_email: str
    esewa_product_code: str
    esewa_secret_key: str
    esewa_form_url: str
    esewa_status_url: str
    esewa_success_url: str
    esewa_failure_url: str
    cloudinary_cloud_name: str
    cloudinary_api_key: str
    cloudinary_api_secret: str
    cloudinary_upload_preset: str
    cloudinary_profile_folder: str
    cloudinary_chat_folder: str
    cloudinary_verification_folder: str


def invalidate_integration_cache() -> None:
    cache.delete(CACHE_KEY)


def _pick_str(db_value, env_value, default: str = "") -> str:
    if db_value is not None and str(db_value).strip():
        return str(db_value).strip()
    if env_value is not None and str(env_value).strip():
        return str(env_value).strip()
    return default


def _pick_int(db_value, env_value, default: int) -> int:
    if db_value is not None:
        return int(db_value)
    if env_value is not None:
        try:
            return int(env_value)
        except (TypeError, ValueError):
            pass
    return default


def _pick_bool(db_value, env_value, default: bool) -> bool:
    if db_value is not None:
        return bool(db_value)
    if env_value is not None:
        return bool(env_value)
    return default


def get_integration_settings() -> IntegrationSettings:
    cached = cache.get(CACHE_KEY)
    if cached is not None:
        return cached

    row = None
    try:
        from site_config.models import SiteSettings

        row = SiteSettings.objects.filter(pk=SiteSettings.SINGLETON_PK).first()
    except Exception:
        row = None

    def db(name):
        return getattr(row, name, None) if row else None

    email_user = _pick_str(db("email_host_user"), settings.EMAIL_HOST_USER)
    default_from = _pick_str(db("default_from_email"), settings.DEFAULT_FROM_EMAIL)
    if not default_from and email_user:
        default_from = f"Duo <{email_user}>"

    uris_raw = _pick_str(db("google_allowed_redirect_uris"), "")
    if uris_raw:
        allowed = tuple(
            uri.strip().rstrip("/") for uri in uris_raw.split(",") if uri.strip()
        )
    else:
        allowed = tuple(settings.GOOGLE_OAUTH_ALLOWED_REDIRECT_URIS)

    redirect_uri = _pick_str(
        db("google_redirect_uri"),
        settings.GOOGLE_OAUTH_REDIRECT_URI,
    )
    if not allowed and redirect_uri:
        allowed = (redirect_uri.rstrip("/"),)

    cfg = IntegrationSettings(
        google_client_id=_pick_str(db("google_client_id"), settings.GOOGLE_OAUTH_CLIENT_ID),
        google_client_secret=_pick_str(
            db("google_client_secret"), settings.GOOGLE_OAUTH_CLIENT_SECRET
        ),
        google_redirect_uri=redirect_uri,
        google_allowed_redirect_uris=allowed,
        email_host=_pick_str(db("email_host"), settings.EMAIL_HOST, "smtp.gmail.com"),
        email_port=_pick_int(db("email_port"), settings.EMAIL_PORT, 587),
        email_use_tls=_pick_bool(db("email_use_tls"), settings.EMAIL_USE_TLS, True),
        email_host_user=email_user,
        email_host_password=_pick_str(
            db("email_host_password"),
            settings.EMAIL_HOST_PASSWORD,
        ).replace(" ", ""),
        email_delivery=_pick_str(
            db("email_delivery"),
            getattr(settings, "EMAIL_DELIVERY", "resend"),
            "resend",
        ),
        resend_api_key=_pick_str(
            db("resend_api_key"),
            getattr(settings, "RESEND_API_KEY", ""),
        ),
        default_from_email=default_from,
        esewa_product_code=_pick_str(db("esewa_product_code"), settings.ESEWA_PRODUCT_CODE),
        esewa_secret_key=_pick_str(db("esewa_secret_key"), settings.ESEWA_SECRET_KEY),
        esewa_form_url=_pick_str(
            db("esewa_form_url"),
            settings.ESEWA_FORM_URL,
            "https://rc-epay.esewa.com.np/api/epay/main/v2/form",
        ),
        esewa_status_url=_pick_str(
            db("esewa_status_url"),
            settings.ESEWA_STATUS_URL,
            "https://rc.esewa.com.np/api/epay/transaction/status/",
        ),
        esewa_success_url=_pick_str(db("esewa_success_url"), settings.ESEWA_SUCCESS_URL),
        esewa_failure_url=_pick_str(db("esewa_failure_url"), settings.ESEWA_FAILURE_URL),
        cloudinary_cloud_name=_pick_str(
            db("cloudinary_cloud_name"), settings.CLOUDINARY_CLOUD_NAME
        ),
        cloudinary_api_key=_pick_str(db("cloudinary_api_key"), settings.CLOUDINARY_API_KEY),
        cloudinary_api_secret=_pick_str(
            db("cloudinary_api_secret"), settings.CLOUDINARY_API_SECRET
        ),
        cloudinary_upload_preset=_pick_str(
            db("cloudinary_upload_preset"), settings.CLOUDINARY_UPLOAD_PRESET
        ),
        cloudinary_profile_folder=_pick_str(
            db("cloudinary_profile_folder"),
            settings.CLOUDINARY_PROFILE_FOLDER,
            "duo/profile_photos",
        ),
        cloudinary_chat_folder=_pick_str(
            db("cloudinary_chat_folder"),
            settings.CLOUDINARY_CHAT_FOLDER,
            "duo/chat_media",
        ),
        cloudinary_verification_folder=_pick_str(
            db("cloudinary_verification_folder"),
            settings.CLOUDINARY_VERIFICATION_FOLDER,
            "duo/verification_selfies",
        ),
    )

    cache.set(CACHE_KEY, cfg, CACHE_TTL_SECONDS)
    return cfg
