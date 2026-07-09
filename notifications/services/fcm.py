from __future__ import annotations

import json
import logging
from typing import Any

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


class FCMError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


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
        title: str,
        body: str,
        data: dict[str, str] | None = None,
        link: str = "",
    ) -> bool:
        if not self.is_configured():
            return False

        payload: dict[str, Any] = {
            "message": {
                "token": token,
                "notification": {
                    "title": title,
                    "body": body,
                },
            }
        }
        if data:
            payload["message"]["data"] = {key: str(value) for key, value in data.items()}
        if link:
            payload["message"]["webpush"] = {"fcm_options": {"link": link}}

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
            if response.status_code in {404, 410}:
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
    ) -> int:
        from notifications.models import DeviceToken

        tokens = list(
            DeviceToken.objects.filter(user_id=user_id, is_active=True).values_list(
                "token", flat=True
            )
        )
        sent = 0
        for token in tokens:
            if self.send_to_token(token, title=title, body=body, data=data, link=link):
                sent += 1
        return sent
