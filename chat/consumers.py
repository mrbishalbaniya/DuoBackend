import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from .models import Conversation, Message, MessageReaction

class ChatConsumer(AsyncWebsocketConsumer):
    async def keen_connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'chat_{self.conversation_id}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def connect(self):
        await self.keen_connect()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Receive message from WebSocket
    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')

        if message_type == 'chat_message':
            content = data.get('content', '')
            image_url = data.get('image_url', '')
            user_id = data.get('user_id')
            
            # Save message to database
            saved_msg = await self.save_message(user_id, content, image_url)
            
            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'id': saved_msg['id'],
                    'content': saved_msg['content'],
                    'image_url': saved_msg['image_url'],
                    'sender_name': saved_msg['sender_name'],
                    'sender_id': user_id,
                    'timestamp': saved_msg['timestamp'],
                }
            )
        
        elif message_type == 'delete_message':
            message_id = data.get('id')
            delete_type = data.get('delete_type') # 'for_me' or 'for_everyone'
            user_id = data.get('user_id')
            
            success = await self.delete_message_action(message_id, user_id, delete_type)
            if success:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'message_deleted',
                        'id': message_id,
                        'user_id': user_id,
                        'delete_type': delete_type
                    }
                )

        elif message_type == 'message_reaction':
            message_id = data.get('id')
            user_id = data.get('user_id')
            emoji = data.get('emoji')
            
            reactions = await self.react_to_message(message_id, user_id, emoji)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_reacted',
                    'id': message_id,
                    'reactions': reactions
                }
            )

        elif message_type == 'typing':
            user_id = data.get('user_id')
            is_typing = data.get('is_typing')
            
            # Broadcast typing status to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'typing_status',
                    'user_id': user_id,
                    'is_typing': is_typing,
                }
            )

    # Receive message from room group
    async def chat_message(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'id': event['id'],
            'content': event['content'],
            'image_url': event.get('image_url', ''),
            'sender_name': event['sender_name'],
            'sender_id': event['sender_id'],
            'timestamp': event['timestamp'],
        }))

    async def typing_status(self, event):
        # Send typing status to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'typing_status',
            'user_id': event['user_id'],
            'is_typing': event['is_typing'],
        }))

    async def message_deleted(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message_deleted',
            'id': event['id'],
            'user_id': event['user_id'],
            'delete_type': event['delete_type']
        }))

    async def message_reacted(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message_reacted',
            'id': event['id'],
            'reactions': event['reactions']
        }))

    @database_sync_to_async
    def save_message(self, user_id, content, image_url=''):
        user = User.objects.get(id=user_id)
        convo = Conversation.objects.get(id=self.conversation_id)
        msg = Message.objects.create(
            conversation=convo,
            sender=user,
            content=content,
            image_url=image_url
        )
        return {
            'id': msg.id,
            'content': msg.content,
            'image_url': msg.image_url,
            'sender_name': user.profile.full_name or user.username,
            'timestamp': msg.timestamp.isoformat(),
        }

    @database_sync_to_async
    def delete_message_action(self, message_id, user_id, delete_type):
        try:
            msg = Message.objects.get(id=message_id)
            user = User.objects.get(id=user_id)
            if delete_type == 'for_everyone':
                # Only sender can delete for everyone
                if msg.sender == user:
                    msg.is_deleted_for_everyone = True
                    msg.save()
                    return True
            else: # for_me
                msg.deleted_by.add(user)
                return True
        except Message.DoesNotExist:
            pass
        return False

    @database_sync_to_async
    def react_to_message(self, message_id, user_id, emoji):
        try:
            msg = Message.objects.get(id=message_id)
            user = User.objects.get(id=user_id)
            
            # Toggle reaction
            existing = MessageReaction.objects.filter(message=msg, user=user, emoji=emoji)
            if existing.exists():
                existing.delete()
            else:
                MessageReaction.objects.create(message=msg, user=user, emoji=emoji)
            
            # Return new summary
            reactions = msg.reactions.all()
            summary = {}
            for r in reactions:
                summary[r.emoji] = summary.get(r.emoji, 0) + 1
            return summary
        except Message.DoesNotExist:
            return {}
