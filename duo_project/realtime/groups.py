"""Channel layer group naming conventions."""


def user_inbox(user_id: int) -> str:
    return f"user_{user_id}"


def chat_room(conversation_id: str | int) -> str:
    return f"chat_{conversation_id}"


def call_room(conversation_id: str | int) -> str:
    return f"call_{conversation_id}"


def activity_feed() -> str:
    return "activity_feed"
