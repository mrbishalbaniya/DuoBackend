"""Broadcast chat events to connected WebSocket clients."""

from __future__ import annotations

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def _send_to_chat_room(conversation_id: int | str, event: dict) -> None:
    layer = get_channel_layer()
    if not layer:
        return
    async_to_sync(layer.group_send)(f"chat_{conversation_id}", event)


def broadcast_chat_message(
    conversation_id: int | str,
    *,
    msg_id: int,
    content: str,
    image_url: str,
    sender_id: int,
    sender_name: str,
    timestamp: str,
) -> None:
    _send_to_chat_room(
        conversation_id,
        {
            "type": "chat_message",
            "id": msg_id,
            "content": content,
            "image_url": image_url or "",
            "sender_name": sender_name,
            "sender_id": sender_id,
            "timestamp": timestamp,
        },
    )


def broadcast_typing_status(
    conversation_id: int | str,
    *,
    user_id: int,
    is_typing: bool = True,
) -> None:
    _send_to_chat_room(
        conversation_id,
        {
            "type": "typing_status",
            "user_id": user_id,
            "is_typing": is_typing,
        },
    )
