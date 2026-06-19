import firebase_admin
from pathlib import Path

from django.conf import settings
from firebase_admin import auth, credentials

_app = None


def get_firebase_app():
    global _app
    if _app is not None:
        return _app

    if not settings.FIREBASE_PROJECT_ID:
        raise ValueError("Firebase is not configured.")

    cred_path = Path(settings.FIREBASE_CREDENTIALS_PATH)
    if not cred_path.exists():
        raise ValueError(
            f"Firebase service account file not found at {cred_path}. "
            "Download it from Firebase Console → Project settings → Service accounts."
        )

    cred = credentials.Certificate(str(cred_path))
    _app = firebase_admin.initialize_app(cred, {"projectId": settings.FIREBASE_PROJECT_ID})
    return _app


def verify_firebase_id_token(token: str) -> dict:
    get_firebase_app()
    return auth.verify_id_token(token)


def normalize_phone(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    if not digits:
        return ""
    if value.strip().startswith("+"):
        return f"+{digits}"
    return digits
