"""Runtime integration settings: admin DB values override django.conf.settings env defaults."""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache

from duo_project.secret_fields import decrypt_secret

CACHE_KEY = "site_config:integration:v2"
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
    email_use_ssl: bool
    email_host_user: str
    email_host_password: str
    email_delivery: str
    nodemailer_relay_url: str
    email_relay_secret: str
    resend_api_key: str
    default_from_email: str
    email_from_name: str
    email_brand_logo_url: str
    email_brand_primary_color: str
    email_footer_text: str
    email_social_links: str
    esewa_product_code: str
    esewa_secret_key: str
    esewa_form_url: str
    esewa_status_url: str
    esewa_success_url: str
    esewa_failure_url: str
    esewa_mobile_client_id: str
    esewa_mobile_secret_key: str
    esewa_mobile_live: bool
    cloudinary_cloud_name: str
    cloudinary_api_key: str
    cloudinary_api_secret: str
    cloudinary_upload_preset: str
    cloudinary_profile_folder: str
    cloudinary_chat_folder: str
    cloudinary_verification_folder: str
    openweather_api_key: str
    fcm_enabled: bool
    firebase_project_id: str
    firebase_api_key: str
    firebase_auth_domain: str
    firebase_messaging_sender_id: str
    firebase_app_id: str
    firebase_android_app_id: str
    firebase_ios_app_id: str
    fcm_vapid_key: str
    firebase_service_account_json: str
    webrtc_stun_urls: tuple[str, ...]
    webrtc_turn_url: str
    webrtc_turn_username: str
    webrtc_turn_credential: str
    webrtc_turn_secret: str
    webrtc_turn_ttl: int


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
        default_from = f"SajiloWork <{email_user}>"

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

    # Always trust the configured frontend + backend OAuth callbacks.
    auto_allowed: list[str] = []
    frontend_url = getattr(settings, "FRONTEND_URL", "").strip().rstrip("/")
    if frontend_url:
        auto_allowed.append(f"{frontend_url}/api/auth/google/callback")
    if redirect_uri:
        auto_allowed.append(redirect_uri.rstrip("/"))
    allowed_set = {uri.rstrip("/") for uri in allowed if uri}
    for uri in auto_allowed:
        allowed_set.add(uri.rstrip("/"))
    allowed = tuple(sorted(allowed_set))

    stun_db = db("webrtc_stun_urls")
    if stun_db is not None and str(stun_db).strip():
        webrtc_stun_urls = tuple(
            url.strip() for url in str(stun_db).split(",") if url.strip()
        )
    else:
        webrtc_stun_urls = tuple(getattr(settings, "WEBRTC_STUN_URLS", ()))

    cfg = IntegrationSettings(
        google_client_id=_pick_str(db("google_client_id"), settings.GOOGLE_OAUTH_CLIENT_ID),
        google_client_secret=decrypt_secret(
            _pick_str(db("google_client_secret"), settings.GOOGLE_OAUTH_CLIENT_SECRET)
        ),
        google_redirect_uri=redirect_uri,
        google_allowed_redirect_uris=allowed,
        email_host=_pick_str(db("email_host"), settings.EMAIL_HOST, ""),
        email_port=_pick_int(db("email_port"), settings.EMAIL_PORT, 587),
        email_use_tls=_pick_bool(db("email_use_tls"), settings.EMAIL_USE_TLS, True),
        email_use_ssl=_pick_bool(
            db("email_use_ssl"),
            getattr(settings, "EMAIL_USE_SSL", False),
            False,
        ),
        email_host_user=email_user,
        email_host_password=decrypt_secret(
            _pick_str(db("email_host_password"), settings.EMAIL_HOST_PASSWORD)
        ).replace(" ", ""),
        email_delivery=_pick_str(
            db("email_delivery"),
            getattr(settings, "EMAIL_DELIVERY", "nodemailer"),
            "nodemailer",
        ),
        nodemailer_relay_url=_pick_str(
            db("nodemailer_relay_url"),
            getattr(settings, "NODEMAILER_RELAY_URL", ""),
        ),
        email_relay_secret=decrypt_secret(
            _pick_str(db("email_relay_secret"), getattr(settings, "EMAIL_RELAY_SECRET", ""))
        ),
        resend_api_key=decrypt_secret(
            _pick_str(db("resend_api_key"), getattr(settings, "RESEND_API_KEY", ""))
        ),
        default_from_email=default_from,
        email_from_name=_pick_str(
            db("email_from_name"),
            getattr(settings, "EMAIL_FROM_NAME", "SajiloWork"),
            "SajiloWork",
        ),
        email_brand_logo_url=_pick_str(
            db("email_brand_logo_url"),
            getattr(settings, "EMAIL_BRAND_LOGO_URL", ""),
        ),
        email_brand_primary_color=_pick_str(
            db("email_brand_primary_color"),
            getattr(settings, "EMAIL_BRAND_PRIMARY_COLOR", "#6366f1"),
            "#6366f1",
        ),
        email_footer_text=_pick_str(
            db("email_footer_text"),
            getattr(settings, "EMAIL_FOOTER_TEXT", "© SajiloWork. All rights reserved."),
            "© SajiloWork. All rights reserved.",
        ),
        email_social_links=_pick_str(
            db("email_social_links"),
            getattr(settings, "EMAIL_SOCIAL_LINKS", ""),
        ),
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
        esewa_mobile_client_id=_pick_str(
            db("esewa_mobile_client_id"),
            settings.ESEWA_MOBILE_CLIENT_ID,
        ),
        esewa_mobile_secret_key=_pick_str(
            db("esewa_mobile_secret_key"),
            settings.ESEWA_MOBILE_SECRET_KEY,
        ),
        esewa_mobile_live=bool(
            db("esewa_mobile_live")
            if db("esewa_mobile_live") is not None
            else settings.ESEWA_MOBILE_LIVE
        ),
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
        openweather_api_key=decrypt_secret(
            _pick_str(db("openweather_api_key"), getattr(settings, "OPENWEATHER_API_KEY", ""))
        ),
        fcm_enabled=_pick_bool(db("fcm_enabled"), getattr(settings, "FCM_ENABLED", False), False),
        firebase_project_id=_pick_str(
            db("firebase_project_id"), getattr(settings, "FIREBASE_PROJECT_ID", "")
        ),
        firebase_api_key=_pick_str(db("firebase_api_key"), getattr(settings, "FIREBASE_API_KEY", "")),
        firebase_auth_domain=_pick_str(
            db("firebase_auth_domain"), getattr(settings, "FIREBASE_AUTH_DOMAIN", "")
        ),
        firebase_messaging_sender_id=_pick_str(
            db("firebase_messaging_sender_id"),
            getattr(settings, "FIREBASE_MESSAGING_SENDER_ID", ""),
        ),
        firebase_app_id=_pick_str(db("firebase_app_id"), getattr(settings, "FIREBASE_APP_ID", "")),
        firebase_android_app_id=_pick_str(
            db("firebase_android_app_id"),
            getattr(settings, "FIREBASE_ANDROID_APP_ID", ""),
        ),
        firebase_ios_app_id=_pick_str(
            db("firebase_ios_app_id"),
            getattr(settings, "FIREBASE_IOS_APP_ID", ""),
        ),
        fcm_vapid_key=_pick_str(db("fcm_vapid_key"), getattr(settings, "FCM_VAPID_KEY", "")),
        firebase_service_account_json=decrypt_secret(
            _pick_str(
                db("firebase_service_account_json"),
                getattr(settings, "FIREBASE_SERVICE_ACCOUNT_JSON", ""),
            )
        ),
        webrtc_stun_urls=webrtc_stun_urls,
        webrtc_turn_url=_pick_str(db("webrtc_turn_url"), getattr(settings, "WEBRTC_TURN_URL", "")),
        webrtc_turn_username=_pick_str(
            db("webrtc_turn_username"),
            getattr(settings, "WEBRTC_TURN_USERNAME", ""),
        ),
        webrtc_turn_credential=decrypt_secret(
            _pick_str(db("webrtc_turn_credential"), getattr(settings, "WEBRTC_TURN_CREDENTIAL", ""))
        ),
        webrtc_turn_secret=decrypt_secret(
            _pick_str(db("webrtc_turn_secret"), getattr(settings, "WEBRTC_TURN_SECRET", ""))
        ),
        webrtc_turn_ttl=_pick_int(
            db("webrtc_turn_ttl"),
            getattr(settings, "WEBRTC_TURN_TTL", 86400),
            86400,
        ),
    )

    cache.set(CACHE_KEY, cfg, CACHE_TTL_SECONDS)
    return cfg
