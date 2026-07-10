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
    message_type: str = "text",
    reply_to: dict | None = None,
    client_temp_id: str | None = None,
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
            "message_type": message_type,
            "reply_to": reply_to,
            "client_temp_id": client_temp_id,
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


def broadcast_message_deleted(
    conversation_id: int | str,
    *,
    message_id: int,
    user_id: int,
    delete_type: str,
) -> None:
    _send_to_chat_room(
        conversation_id,
        {
            "type": "message_deleted",
            "id": message_id,
            "user_id": user_id,
            "delete_type": delete_type,
        },
    )


def broadcast_message_reacted(
    conversation_id: int | str,
    *,
    message_id: int,
    user_id: int,
    emoji: str,
    reactions: dict[str, list[int]],
) -> None:
    _send_to_chat_room(
        conversation_id,
        {
            "type": "message_reacted",
            "id": message_id,
            "user_id": user_id,
            "emoji": emoji,
            "reactions": reactions,
        },
    )


def broadcast_messages_read(
    conversation_id: int | str,
    *,
    reader_id: int,
    message_ids: list[int],
) -> None:
    if not message_ids:
        return
    _send_to_chat_room(
        conversation_id,
        {
            "type": "messages_read",
            "reader_id": reader_id,
            "message_ids": message_ids,
        },
    )
