import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

from .realtime import ACTIVITY_GROUP
from .services.zones import compute_activity_zones, filter_zones_for_flags


class ActivityConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.user = user
        self.viewport: dict | None = None
        await self.channel_layer.group_add(ACTIVITY_GROUP, self.channel_name)
        await self.accept()
        await self.send_zones()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(ACTIVITY_GROUP, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        if data.get("type") == "viewport":
            self.viewport = {
                "lat_min": float(data["lat_min"]),
                "lat_max": float(data["lat_max"]),
                "lon_min": float(data["lon_min"]),
                "lon_max": float(data["lon_max"]),
                "zoom": float(data.get("zoom", 4)),
                "trending": bool(data.get("trending")),
                "events": bool(data.get("events")),
                "friends": bool(data.get("friends")),
                "nearby": bool(data.get("nearby")),
                "user_lat": data.get("user_lat"),
                "user_lng": data.get("user_lng"),
                "nearby_km": float(data.get("nearby_km", 120)),
            }
            await self.send_zones()

    async def activity_refresh(self, event):
        await self.send_zones()

    async def send_zones(self):
        viewport = self.viewport
        if not viewport:
            await self.send(json.dumps({"type": "zones", "zones": []}))
            return

        zones = await self._zones_for_viewport(viewport)
        await self.send(json.dumps({"type": "zones", "zones": zones}))

    @database_sync_to_async
    def _zones_for_viewport(self, viewport: dict):
        zones = compute_activity_zones(
            lat_min=viewport["lat_min"],
            lat_max=viewport["lat_max"],
            lon_min=viewport["lon_min"],
            lon_max=viewport["lon_max"],
            zoom=viewport.get("zoom", 4),
            user=self.user,
        )
        if viewport.get("trending"):
            zones = filter_zones_for_flags(zones, trending_only=True)
        if viewport.get("events"):
            zones = filter_zones_for_flags(zones, events_only=True)
        if viewport.get("friends"):
            zones = filter_zones_for_flags(zones, friends_only=True)
        if viewport.get("nearby") and viewport.get("user_lat") is not None:
            zones = filter_zones_for_flags(
                zones,
                nearby_km=viewport.get("nearby_km", 120),
                user_lat=float(viewport["user_lat"]),
                user_lng=float(viewport["user_lng"]),
            )
        return zones
