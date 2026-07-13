import asyncio
import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

from calls.models import CallSession
from calls.services import get_call_for_user, relay_signaling_event
from chat.models import Conversation
from chat.services import conversation_is_blocked
from duo_project.realtime.groups import call_room, user_inbox
from duo_project.realtime.presence import mark_active
from duo_project.realtime.registry import register_connection, touch_connection, unregister_connection
from duo_project.realtime.throttle import allow_event

logger = logging.getLogger("duo.calls")

HEARTBEAT_INTERVAL = 30

SIGNALING_EVENTS = {
    "call_invite",
    "call_accept",
    "call_reject",
    "call_busy",
    "call_cancel",
    "call_hangup",
    "call_offer",
    "call_answer",
    "ice_candidate",
    "call_reconnect",
    "call_quality",
}


class CallSignalingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.user = user
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.room_group_name = call_room(self.conversation_id)
        self.inbox_group_name = user_inbox(user.id)

        is_member = await self.verify_membership()
        if not is_member:
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.channel_layer.group_add(self.inbox_group_name, self.channel_name)

        if not register_connection(user.id, self.channel_name, socket_type="call"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
            await self.channel_layer.group_discard(self.inbox_group_name, self.channel_name)
            await self.close(code=4429)
            return

        await self.accept()
        mark_active(user.id)
        await self.send(
            text_data=json.dumps(
                {
                    "type": "connected",
                    "conversation_id": str(self.conversation_id),
                    "channel": "call",
                }
            )
        )
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def disconnect(self, close_code):
        if hasattr(self, "_heartbeat_task"):
            self._heartbeat_task.cancel()
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        if hasattr(self, "inbox_group_name"):
            await self.channel_layer.group_discard(self.inbox_group_name, self.channel_name)
        if hasattr(self, "user"):
            unregister_connection(self.user.id, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self._send_error("invalid_json", "Malformed JSON payload.")
            return

        message_type = (data.get("type") or "").strip()
        if not allow_event(self.user.id, message_type):
            await self._send_error("rate_limited", "Too many events. Slow down.")
            return

        touch_connection(self.user.id, self.channel_name)

        if message_type == "ping":
            mark_active(self.user.id)
            await self.send(text_data=json.dumps({"type": "pong", "ts": data.get("ts")}))
            return

        if message_type not in SIGNALING_EVENTS:
            await self._send_error("unknown_event", f"Unsupported event: {message_type}")
            return

        call_id = (data.get("call_id") or "").strip()
        if not call_id:
            await self._send_error("missing_call_id", "call_id is required.")
            return

        call, error = await self.get_call(call_id)
        if error:
            await self._send_error("forbidden", error)
            return

        payload = data.get("payload") or {}
        if message_type in {"call_offer", "call_answer"}:
            payload = {
                "sdp": data.get("sdp") or payload.get("sdp"),
                "type": data.get("sdp_type") or payload.get("type"),
            }
        elif message_type == "ice_candidate":
            payload = {
                "candidate": data.get("candidate") or payload.get("candidate"),
                "sdpMid": data.get("sdp_mid") or payload.get("sdpMid"),
                "sdpMLineIndex": data.get("sdp_mline_index", payload.get("sdpMLineIndex")),
            }

        await self.relay(call, message_type, payload)

        await self.send(
            text_data=json.dumps(
                {
                    "type": "signal_ack",
                    "event": message_type,
                    "call_id": call_id,
                }
            )
        )

    async def call_signal(self, event):
        message = event.get("message") or {}
        if message.get("sender_id") == self.user.id:
            return
        await self.send(text_data=json.dumps(message))

    async def inbox_event(self, event):
        """Forward user-inbox call lifecycle events onto the call socket."""
        event_type = event.get("event_type") or "notification"
        payload = event.get("payload") or {}
        await self.send(
            text_data=json.dumps(
                {
                    "type": event_type,
                    **payload,
                }
            )
        )

    async def _heartbeat_loop(self):
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                await self.send(text_data=json.dumps({"type": "ping"}))
        except asyncio.CancelledError:
            return

    async def _send_error(self, code: str, detail: str) -> None:
        await self.send(text_data=json.dumps({"type": "error", "code": code, "detail": detail}))

    @database_sync_to_async
    def verify_membership(self) -> bool:
        try:
            key = str(self.conversation_id).strip()
            convo = Conversation.objects.select_related("match").filter(public_id=key).first()
            if not convo and key.isdigit():
                convo = Conversation.objects.select_related("match").filter(id=int(key)).first()
            if not convo:
                return False
            match = convo.match
            if self.user.id not in (match.user1_id, match.user2_id):
                return False
            return not conversation_is_blocked(convo, self.user)
        except Exception:
            return False

    @database_sync_to_async
    def get_call(self, public_id: str):
        return get_call_for_user(public_id, self.user)

    @database_sync_to_async
    def relay(self, call: CallSession, event_type: str, payload: dict) -> None:
        relay_signaling_event(
            call=call,
            sender_id=self.user.id,
            event_type=event_type,
            payload=payload,
        )
