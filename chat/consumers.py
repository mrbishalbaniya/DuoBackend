import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from .models import Conversation, Message, MessageReaction


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

            saved_msg = await self.save_message(user_id, content, image_url)
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

            reactions = await self.react_to_message(message_id, user_id, emoji)
            if reactions is not None:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "message_reacted",
                        "id": message_id,
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
                    "reactions": event["reactions"],
                }
            )
        )

    @database_sync_to_async
    def verify_membership(self):
        try:
            convo = Conversation.objects.select_related("match").get(id=self.conversation_id)
            match = convo.match
            return self.user.id in (match.user1_id, match.user2_id)
        except Conversation.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, user_id, content, image_url=""):
        try:
            convo = Conversation.objects.select_related("match").get(id=self.conversation_id)
            match = convo.match
            if user_id not in (match.user1_id, match.user2_id):
                return None
            user = match.user1 if match.user1_id == user_id else match.user2
            msg = Message.objects.create(
                conversation=convo,
                sender=user,
                content=content,
                image_url=image_url,
            )
            from notifications.dispatch import dispatch_chat_message_push

            dispatch_chat_message_push(msg)
            return {
                "id": msg.id,
                "content": msg.content,
                "image_url": msg.image_url,
                "sender_name": user.profile.full_name or user.username,
                "timestamp": msg.timestamp.isoformat(),
            }
        except Conversation.DoesNotExist:
            return None

    @database_sync_to_async
    def delete_message_action(self, message_id, user_id, delete_type):
        try:
            msg = Message.objects.select_related("conversation__match").get(id=message_id)
            convo = msg.conversation
            match = convo.match
            if user_id not in (match.user1_id, match.user2_id):
                return False
            if convo.id != int(self.conversation_id):
                return False

            user = match.user1 if match.user1_id == user_id else match.user2
            if delete_type == "for_everyone":
                if msg.sender_id == user_id:
                    msg.is_deleted_for_everyone = True
                    msg.save()
                    return True
            else:
                msg.deleted_by.add(user)
                return True
        except Message.DoesNotExist:
            pass
        return False

    @database_sync_to_async
    def react_to_message(self, message_id, user_id, emoji):
        try:
            msg = Message.objects.select_related("conversation__match").get(id=message_id)
            convo = msg.conversation
            match = convo.match
            if user_id not in (match.user1_id, match.user2_id):
                return None
            if convo.id != int(self.conversation_id):
                return None

            user = match.user1 if match.user1_id == user_id else match.user2
            existing = MessageReaction.objects.filter(message=msg, user=user, emoji=emoji)
            if existing.exists():
                existing.delete()
            else:
                MessageReaction.objects.create(message=msg, user=user, emoji=emoji)

            reactions = msg.reactions.all()
            summary = {}
            for reaction in reactions:
                summary[reaction.emoji] = summary.get(reaction.emoji, 0) + 1
            return summary
        except Message.DoesNotExist:
            return None
