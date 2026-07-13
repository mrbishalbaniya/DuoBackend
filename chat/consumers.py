import asyncio
import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

from duo_project.realtime.groups import chat_room, user_inbox
from duo_project.realtime.presence import mark_active
from duo_project.realtime.registry import register_connection, touch_connection, unregister_connection
from duo_project.realtime.throttle import allow_event
from .models import Conversation, Message
from .services import (
    conversation_is_blocked,
    create_security_system_message,
    delete_message_for_user,
    edit_message,
    infer_message_type,
    mark_messages_delivered,
    mark_messages_read,
    react_to_message,
    sanitize_message_content,
    touch_conversation_activity,
)

logger = logging.getLogger("duo.realtime")

HEARTBEAT_INTERVAL = 30


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.user = user
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.room_group_name = chat_room(self.conversation_id)
        self.inbox_group_name = user_inbox(user.id)

        is_member = await self.verify_membership()
        if not is_member:
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.channel_layer.group_add(self.inbox_group_name, self.channel_name)

        if not register_connection(user.id, self.channel_name, socket_type="chat"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
            await self.channel_layer.group_discard(self.inbox_group_name, self.channel_name)
            await self.close(code=4429)
            return

        await self.accept()

        mark_active(user.id)
        await self.mark_delivered_on_connect()
        await self.send(text_data=json.dumps({"type": "connected", "conversation_id": str(self.conversation_id)}))
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
        user_id = self.user.id

        if message_type == "ping":
            mark_active(user_id)
            await self.send(text_data=json.dumps({"type": "pong", "ts": data.get("ts")}))
            return

        if message_type == "chat_message":
            content = data.get("content", "")
            image_url = data.get("image_url", "")
            reply_to_id = data.get("reply_to_id")
            client_temp_id = data.get("client_temp_id")

            saved_msg = await self.save_message(
                user_id,
                content,
                image_url,
                reply_to_id=reply_to_id,
            )
            if not saved_msg:
                await self._send_error("send_failed", "Could not send message.")
                return

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "id": saved_msg["id"],
                    "content": saved_msg["content"],
                    "image_url": saved_msg["image_url"],
                    "sender_name": saved_msg["sender_name"],
                    "sender_id": user_id,
                    "timestamp": saved_msg["timestamp"],
                    "message_type": saved_msg["message_type"],
                    "reply_to": saved_msg.get("reply_to"),
                    "client_temp_id": client_temp_id,
                },
            )
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "message_ack",
                        "id": saved_msg["id"],
                        "client_temp_id": client_temp_id,
                        "status": "sent",
                    }
                )
            )

        elif message_type == "edit_message":
            message_id = data.get("id")
            content = data.get("content", "")
            edited = await self.edit_message_action(message_id, user_id, content)
            if edited:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "message_edited",
                        "id": edited["id"],
                        "content": edited["content"],
                        "edited_at": edited["edited_at"],
                        "sender_id": user_id,
                    },
                )

        elif message_type == "delete_message":
            message_id = data.get("id")
            delete_type = data.get("delete_type")

            success = await self.delete_message_action(message_id, user_id, delete_type)
            if success:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "message_deleted",
                        "id": message_id,
                        "user_id": user_id,
                        "delete_type": delete_type,
                    },
                )

        elif message_type == "message_reaction":
            message_id = data.get("id")
            emoji = data.get("emoji")

            result = await self.react_to_message_action(message_id, user_id, emoji)
            if result is not None:
                reactions, applied_emoji = result
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "message_reacted",
                        "id": message_id,
                        "user_id": user_id,
                        "emoji": applied_emoji,
                        "reactions": reactions,
                    },
                )

        elif message_type == "typing":
            is_typing = bool(data.get("is_typing", True))
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "typing_status",
                    "user_id": user_id,
                    "is_typing": is_typing,
                },
            )

        elif message_type == "recording":
            is_recording = bool(data.get("is_recording", True))
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "recording_status",
                    "user_id": user_id,
                    "is_recording": is_recording,
                },
            )

        elif message_type == "upload_progress":
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "upload_progress",
                    "user_id": user_id,
                    "upload_id": data.get("upload_id"),
                    "progress": data.get("progress", 0),
                    "media_type": data.get("media_type", "file"),
                },
            )

        elif message_type == "mark_read":
            read_ids = await self.mark_read_action(user_id)
            if read_ids:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "messages_read",
                        "reader_id": user_id,
                        "message_ids": read_ids,
                    },
                )

        elif message_type == "security_event":
            event_code = data.get("event_code", "")
            saved_msg = await self.record_security_event(user_id, event_code)
            if saved_msg:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "chat_message",
                        "id": saved_msg["id"],
                        "content": saved_msg["content"],
                        "image_url": "",
                        "sender_name": saved_msg["sender_name"],
                        "sender_id": user_id,
                        "timestamp": saved_msg["timestamp"],
                        "message_type": saved_msg["message_type"],
                        "event_code": saved_msg["event_code"],
                    },
                )

    async def chat_message(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "chat_message",
                    "id": event["id"],
                    "content": event["content"],
                    "image_url": event.get("image_url", ""),
                    "sender_name": event["sender_name"],
                    "sender_id": event["sender_id"],
                    "timestamp": event["timestamp"],
                    "message_type": event.get("message_type", "text"),
                    "reply_to": event.get("reply_to"),
                    "client_temp_id": event.get("client_temp_id"),
                    "event_code": event.get("event_code", ""),
                }
            )
        )

    async def typing_status(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "typing_status",
                    "user_id": event["user_id"],
                    "is_typing": event["is_typing"],
                }
            )
        )

    async def recording_status(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "recording_status",
                    "user_id": event["user_id"],
                    "is_recording": event["is_recording"],
                }
            )
        )

    async def upload_progress(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "upload_progress",
                    "user_id": event["user_id"],
                    "upload_id": event.get("upload_id"),
                    "progress": event.get("progress", 0),
                    "media_type": event.get("media_type", "file"),
                }
            )
        )

    async def message_edited(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "message_edited",
                    "id": event["id"],
                    "content": event["content"],
                    "edited_at": event["edited_at"],
                    "sender_id": event["sender_id"],
                }
            )
        )

    async def message_deleted(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "message_deleted",
                    "id": event["id"],
                    "user_id": event["user_id"],
                    "delete_type": event["delete_type"],
                }
            )
        )

    async def message_reacted(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "message_reacted",
                    "id": event["id"],
                    "user_id": event.get("user_id"),
                    "emoji": event.get("emoji"),
                    "reactions": event["reactions"],
                }
            )
        )

    async def messages_read(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "messages_read",
                    "reader_id": event["reader_id"],
                    "message_ids": event["message_ids"],
                }
            )
        )

    async def messages_delivered(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "messages_delivered",
                    "recipient_id": event["recipient_id"],
                    "message_ids": event["message_ids"],
                }
            )
        )

    async def inbox_event(self, event):
        """Forward inbox notifications to chat socket (optional single-socket clients)."""
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

    async def _send_error(self, code: str, message: str) -> None:
        await self.send(text_data=json.dumps({"type": "error", "code": code, "message": message}))

    @database_sync_to_async
    def verify_membership(self):
        try:
            convo = self._get_conversation()
            if not convo:
                return False
            match = convo.match
            if self.user.id not in (match.user1_id, match.user2_id):
                return False
            return not conversation_is_blocked(convo, self.user)
        except Exception:
            return False

    @database_sync_to_async
    def mark_delivered_on_connect(self):
        convo = self._get_conversation()
        if not convo:
            return
        delivered_ids = mark_messages_delivered(convo, self.user)
        if delivered_ids:
            from .realtime import broadcast_messages_delivered

            broadcast_messages_delivered(
                self.conversation_id,
                recipient_id=self.user.id,
                message_ids=delivered_ids,
            )

    def _get_conversation(self):
        key = str(self.conversation_id).strip()
        qs = Conversation.objects.select_related("match")
        convo = qs.filter(public_id=key).first()
        if convo:
            return convo
        if key.isdigit() and len(key) < 10:
            return qs.filter(id=int(key)).first()
        return None

    def _build_reply_payload(self, parent: Message | None) -> dict | None:
        if not parent or parent.is_deleted_for_everyone:
            return None
        return {
            "id": parent.id,
            "content": parent.content,
            "sender_name": getattr(parent.sender.profile, "full_name", "") or parent.sender.username,
            "image_url": parent.image_url or "",
            "message_type": parent.message_type,
        }

    @database_sync_to_async
    def record_security_event(self, user_id, event_code):
        try:
            convo = self._get_conversation()
            if not convo:
                return None
            match = convo.match
            if user_id not in (match.user1_id, match.user2_id):
                return None
            user = match.user1 if match.user1_id == user_id else match.user2
            if conversation_is_blocked(convo, user):
                return None

            msg = create_security_system_message(convo, user, str(event_code or "").strip().upper())
            if not msg:
                return None

            msg = Message.objects.select_related("sender__profile").get(id=msg.id)
            sender_name = getattr(msg.sender.profile, "full_name", "") or msg.sender.username
            return {
                "id": msg.id,
                "content": msg.content,
                "sender_name": sender_name,
                "timestamp": msg.timestamp.isoformat(),
                "message_type": msg.message_type,
                "event_code": msg.event_code,
            }
        except Exception:
            return None

    @database_sync_to_async
    def save_message(self, user_id, content, image_url="", reply_to_id=None):
        try:
            from duo_project.security.media_urls import is_allowed_media_url

            content = sanitize_message_content(content)
            if not content and not (image_url or "").strip():
                return None

            if image_url and not is_allowed_media_url(image_url):
                return None
            convo = self._get_conversation()
            if not convo:
                return None
            match = convo.match
            if user_id not in (match.user1_id, match.user2_id):
                return None
            user = match.user1 if match.user1_id == user_id else match.user2
            if conversation_is_blocked(convo, user):
                return None

            reply_to = None
            if reply_to_id:
                reply_to = convo.messages.filter(id=reply_to_id).first()

            msg = Message.objects.create(
                conversation=convo,
                sender=user,
                content=content,
                image_url=image_url,
                message_type=infer_message_type(content, image_url),
                reply_to=reply_to,
            )
            touch_conversation_activity(convo, msg.timestamp)

            msg = (
                Message.objects.select_related(
                    "sender__profile",
                    "conversation__match",
                    "reply_to",
                    "reply_to__sender__profile",
                )
                .get(id=msg.id)
            )
            from notifications.dispatch import dispatch_chat_message_push

            dispatch_chat_message_push(msg)
            return {
                "id": msg.id,
                "content": msg.content,
                "image_url": msg.image_url,
                "sender_name": user.profile.full_name or user.username,
                "timestamp": msg.timestamp.isoformat(),
                "message_type": msg.message_type,
                "reply_to": self._build_reply_payload(msg.reply_to),
            }
        except Exception:
            return None

    def _conversation_matches(self, convo) -> bool:
        key = str(self.conversation_id).strip()
        if convo.public_id == key:
            return True
        if key.isdigit() and len(key) < 10:
            return convo.id == int(key)
        return False

    @database_sync_to_async
    def edit_message_action(self, message_id, user_id, content):
        try:
            msg = Message.objects.select_related("conversation__match", "sender__profile").get(id=message_id)
            convo = msg.conversation
            match = convo.match
            if user_id not in (match.user1_id, match.user2_id):
                return None
            if not self._conversation_matches(convo):
                return None
            user = match.user1 if match.user1_id == user_id else match.user2
            updated = edit_message(msg, user, content)
            if not updated:
                return None
            return {
                "id": updated.id,
                "content": updated.content,
                "edited_at": updated.edited_at.isoformat() if updated.edited_at else "",
            }
        except Message.DoesNotExist:
            return None

    @database_sync_to_async
    def delete_message_action(self, message_id, user_id, delete_type):
        try:
            msg = Message.objects.select_related("conversation__match").get(id=message_id)
            convo = msg.conversation
            match = convo.match
            if user_id not in (match.user1_id, match.user2_id):
                return False
            if not self._conversation_matches(convo):
                return False

            user = match.user1 if match.user1_id == user_id else match.user2
            return delete_message_for_user(msg, user, delete_type)
        except Message.DoesNotExist:
            pass
        return False

    @database_sync_to_async
    def react_to_message_action(self, message_id, user_id, emoji):
        try:
            msg = Message.objects.select_related("conversation__match").get(id=message_id)
            convo = msg.conversation
            match = convo.match
            if user_id not in (match.user1_id, match.user2_id):
                return None
            if not self._conversation_matches(convo):
                return None

            user = match.user1 if match.user1_id == user_id else match.user2
            reactions = react_to_message(msg, user, emoji)
            return reactions, emoji
        except Message.DoesNotExist:
            return None

    @database_sync_to_async
    def mark_read_action(self, user_id):
        convo = self._get_conversation()
        if not convo:
            return []
        match = convo.match
        if user_id not in (match.user1_id, match.user2_id):
            return []
        user = match.user1 if match.user1_id == user_id else match.user2
        return mark_messages_read(convo, user)
