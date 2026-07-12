import asyncio
import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

from analytics.constants import REALTIME_GROUP
from analytics.services.dashboard.realtime import get_realtime_metrics


class AnalyticsConsumer(AsyncWebsocketConsumer):
    """Staff-only real-time analytics WebSocket."""

    async def connect(self):
        user = self.scope.get("user")
        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close(code=4401)
            return
        if not (user.is_staff or user.is_superuser):
            await self.close(code=4403)
            return

        self.user = user
        await self.channel_layer.group_add(REALTIME_GROUP, self.channel_name)
        await self.accept()
        await self.send_metrics()
        self._poll_task = asyncio.create_task(self._poll_loop())

    async def disconnect(self, close_code):
        if hasattr(self, "_poll_task"):
            self._poll_task.cancel()
        await self.channel_layer.group_discard(REALTIME_GROUP, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return
        if data.get("type") == "refresh":
            await self.send_metrics()

    async def analytics_event(self, event):
        await self.send(json.dumps({
            "type": "event",
            "event_type": event.get("event_type"),
            "payload": event.get("payload", {}),
        }))

    async def analytics_metrics(self, event):
        await self.send(json.dumps({
            "type": "metrics",
            "metrics": event.get("metrics", {}),
        }))

    async def _poll_loop(self):
        try:
            while True:
                await asyncio.sleep(5)
                await self.send_metrics()
        except asyncio.CancelledError:
            return

    async def send_metrics(self):
        metrics = await self._get_metrics()
        await self.send(json.dumps({"type": "metrics", "metrics": metrics}))

    @database_sync_to_async
    def _get_metrics(self):
        return get_realtime_metrics()
