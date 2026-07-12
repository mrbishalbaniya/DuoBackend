from __future__ import annotations

import json
import logging
from typing import Any

import requests
from django.conf import settings
from google.auth.transport.requests import Request
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


class FCMError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _default_icon() -> str:
    frontend = getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")
    return f"{frontend}/icons/duo-notification-192.png"


def _default_badge() -> str:
    frontend = getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")
    return f"{frontend}/icons/duo-badge-96.png"


class FCMService:
    def __init__(self) -> None:
        from duo_project.runtime_config import get_integration_settings

        cfg = get_integration_settings()
        self.enabled = cfg.fcm_enabled
        self.project_id = (cfg.firebase_project_id or "").strip()
        self.service_account_json = (cfg.firebase_service_account_json or "").strip()

    def is_configured(self) -> bool:
        return bool(self.enabled and self.project_id and self.service_account_json)

    def _access_token(self) -> str:
        try:
            info = json.loads(self.service_account_json)
        except json.JSONDecodeError as exc:
            raise FCMError("Firebase service account JSON is invalid.") from exc

        credentials = service_account.Credentials.from_service_account_info(
            info,
            scopes=[FCM_SCOPE],
        )
        credentials.refresh(Request())
        return credentials.token

    def send_to_token(
        self,
        token: str,
        *,
        platform: str = "web",
        title: str,
        body: str,
        data: dict[str, str] | None = None,
        link: str = "",
        icon: str = "",
        image: str = "",
        tag: str = "",
        badge: str = "",
    ) -> bool:
        if not self.is_configured():
            return False

        icon_url = (icon or _default_icon()).strip()
        badge_url = (badge or _default_badge()).strip()
        image_url = (image or "").strip()

        relative_url = ""
        if data and data.get("url"):
            relative_url = str(data["url"])
        elif link:
            frontend = getattr(settings, "FRONTEND_URL", "").rstrip("/")
            if frontend and link.startswith(frontend):
                relative_url = link[len(frontend) :] or "/"
            else:
                relative_url = link

        # Data-only payload so the service worker can render a custom notification
        # (avoids the browser auto-showing a plain duplicate).
        payload_data: dict[str, str] = {
            "title": title,
            "body": body,
            "icon": icon_url,
            "badge": badge_url,
            "url": relative_url or "/message",
        }
        if image_url:
            payload_data["image"] = image_url
        if tag:
            payload_data["tag"] = tag
        if data:
            for key, value in data.items():
                payload_data[str(key)] = str(value)

        webpush: dict[str, Any] = {
            "headers": {
                "Urgency": "high",
                "TTL": "86400",
            },
        }
        if link:
            webpush["fcm_options"] = {"link": link}

        payload: dict[str, Any] = {
            "message": {
                "token": token,
                "data": payload_data,
                "webpush": webpush,
            }
        }

        if platform == "android":
            payload["message"]["android"] = {
                "priority": "HIGH",
            }
        elif platform == "ios":
            payload["message"]["apns"] = {
                "headers": {"apns-priority": "10"},
                "payload": {"aps": {"content-available": 1}},
            }

        headers = {
            "Authorization": f"Bearer {self._access_token()}",
            "Content-Type": "application/json; charset=UTF-8",
        }
        url = (
            f"https://fcm.googleapis.com/v1/projects/{self.project_id}/messages:send"
        )

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=15)
        except requests.RequestException as exc:
            logger.warning("FCM request failed: %s", exc)
            return False

        if response.status_code >= 400:
            logger.warning(
                "FCM rejected token %s…: %s %s",
                token[:12],
                response.status_code,
                response.text[:300],
            )
            if response.status_code in {404, 410} or (
                response.status_code == 400
                and any(
                    marker in response.text
                    for marker in (
                        "UNREGISTERED",
                        "INVALID_ARGUMENT",
                        "NOT_FOUND",
                    )
                )
            ):
                from notifications.models import DeviceToken

                DeviceToken.objects.filter(token=token).update(is_active=False)
            return False

        return True

    def send_to_user(
        self,
        user_id: int,
        *,
        title: str,
        body: str,
        data: dict[str, str] | None = None,
        link: str = "",
        icon: str = "",
        image: str = "",
        tag: str = "",
        badge: str = "",
    ) -> int:
        from notifications.models import DeviceToken

        tokens = list(
            DeviceToken.objects.filter(user_id=user_id, is_active=True).values_list(
                "token", "platform"
            )
        )
        if not tokens:
            logger.debug("No active FCM tokens for user %s", user_id)
            return 0

        sent = 0
        for token, platform in tokens:
            if self.send_to_token(
                token,
                platform=platform or "web",
                title=title,
                body=body,
                data=data,
                link=link,
                icon=icon,
                image=image,
                tag=tag,
                badge=badge,
            ):
                sent += 1
        return sent
