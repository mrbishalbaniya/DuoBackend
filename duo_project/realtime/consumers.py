"""User inbox WebSocket — matches, likes, notifications, presence."""

from __future__ import annotations

import asyncio
import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

from duo_project.realtime.groups import user_inbox
from duo_project.realtime.presence import get_presence, mark_active, mark_offline
from duo_project.realtime.registry import (
    register_connection,
    touch_connection,
    unregister_connection,
)
from duo_project.realtime.throttle import allow_event

logger = logging.getLogger("duo.realtime")

HEARTBEAT_INTERVAL = 30


class InboxConsumer(AsyncWebsocketConsumer):
    """Per-user real-time feed: matches, likes, notifications, presence."""

    async def connect(self):
        user = self.scope.get("user")
        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.user = user
        self.inbox_group = user_inbox(user.id)
        await self.channel_layer.group_add(self.inbox_group, self.channel_name)

        if not register_connection(user.id, self.channel_name, socket_type="inbox"):
            await self.channel_layer.group_discard(self.inbox_group, self.channel_name)
            await self.close(code=4429)
            return

        await self.accept()

        presence = mark_active(user.id)
        await self.send(
            text_data=json.dumps(
                {
                    "type": "connected",
                    "user_id": user.id,
                    "presence": presence,
                }
            )
        )
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def disconnect(self, close_code):
        if hasattr(self, "_heartbeat_task"):
            self._heartbeat_task.cancel()
        if hasattr(self, "inbox_group"):
            await self.channel_layer.group_discard(self.inbox_group, self.channel_name)
        if hasattr(self, "user"):
            unregister_connection(self.user.id, self.channel_name)
            if await self._user_has_no_connections():
                mark_offline(self.user.id)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self._send_error("invalid_json", "Malformed JSON payload.")
            return

        event_type = (data.get("type") or "").strip().lower()
        if not allow_event(self.user.id, event_type):
            await self._send_error("rate_limited", "Too many events. Slow down.")
            return

        touch_connection(self.user.id, self.channel_name)

        if event_type == "ping":
            mark_active(self.user.id)
            await self.send(text_data=json.dumps({"type": "pong", "ts": data.get("ts")}))
            return

        if event_type == "presence_get":
            target_id = int(data.get("user_id") or self.user.id)
            from duo_project.security.privacy import users_can_see_presence

            if not users_can_see_presence(self.user.id, target_id):
                await self._send_error("forbidden", "Presence not available.")
                return
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "presence_update",
                        "user_id": target_id,
                        **get_presence(target_id),
                    }
                )
            )
            return

        if event_type == "presence_subscribe":
            # Client declares active; server refreshes TTL
            presence = mark_active(self.user.id, status=data.get("status", "online"))
            await self.send(
                text_data=json.dumps(
                    {"type": "presence_update", "user_id": self.user.id, **presence}
                )
            )
            return

    async def inbox_event(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": event.get("event_type", "notification"),
                    **(event.get("payload") or {}),
                }
            )
        )

    async def _heartbeat_loop(self):
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                touch_connection(self.user.id, self.channel_name)
                mark_active(self.user.id)
                await self.send(text_data=json.dumps({"type": "ping"}))
        except asyncio.CancelledError:
            return
        except Exception:
            logger.debug("inbox_heartbeat_stopped user_id=%s", self.user.id)

    async def _send_error(self, code: str, message: str) -> None:
        await self.send(text_data=json.dumps({"type": "error", "code": code, "message": message}))

    @database_sync_to_async
    def _user_has_no_connections(self) -> bool:
        from duo_project.realtime.registry import connection_count

        return connection_count(self.user.id) == 0
