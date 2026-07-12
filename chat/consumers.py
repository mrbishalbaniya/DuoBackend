import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from .models import Conversation, Message
from .services import (
    conversation_is_blocked,
    create_security_system_message,
    delete_message_for_user,
    infer_message_type,
    mark_messages_delivered,
    mark_messages_read,
    react_to_message,
    touch_conversation_activity,
)


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.user = user
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.room_group_name = f"chat_{self.conversation_id}"

        is_member = await self.verify_membership()
        if not is_member:
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        await self.mark_delivered_on_connect()

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get("type")
        user_id = self.user.id

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
            is_typing = data.get("is_typing")
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "typing_status",
                    "user_id": user_id,
                    "is_typing": is_typing,
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
        mark_messages_delivered(convo, self.user)

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
