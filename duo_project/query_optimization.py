"""Shared queryset helpers for database performance (no business-logic changes)."""

from __future__ import annotations

from django.db.models import Count, Exists, OuterRef, Prefetch, Q, Subquery
from django.db.models import CharField
from django.db.models.functions import Cast, Concat, MD5

from chat.models import Conversation, ConversationPreference, Message
from matching.models import Match


def get_matched_user_ids(user) -> set[int]:
    """Return user ids the given user has matched with (single indexed query)."""
    if not user or not getattr(user, "is_authenticated", False):
        return set()

    ids: set[int] = set()
    rows = Match.objects.filter(Q(user1=user) | Q(user2=user)).values_list(
        "user1_id", "user2_id"
    )
    user_id = user.id
    for u1, u2 in rows:
        if u1 != user_id:
            ids.add(u1)
        if u2 != user_id:
            ids.add(u2)
    return ids


def parse_list_window(request, *, default_limit: int = 200, max_limit: int = 500) -> tuple[int, int] | None:
    """
    Parse optional ?limit=&offset= for list endpoints.

    Returns None when no pagination params are present (preserve legacy array responses).
    """
    if "limit" not in request.query_params and "offset" not in request.query_params:
        return None

    try:
        limit = int(request.query_params.get("limit", default_limit))
    except (TypeError, ValueError):
        limit = default_limit

    try:
        offset = int(request.query_params.get("offset", 0))
    except (TypeError, ValueError):
        offset = 0

    limit = max(1, min(limit, max_limit))
    offset = max(0, offset)
    return offset, limit


def apply_list_window(queryset, request, *, default_limit: int = 200, max_limit: int = 500):
    """Slice a queryset when ?limit= or ?offset= is provided."""
    window = parse_list_window(request, default_limit=default_limit, max_limit=max_limit)
    if window is None:
        return queryset
    offset, limit = window
    return queryset[offset : offset + limit]


def discover_ordering(queryset, viewer_user_id: int):
    """
    Per-viewer pseudo-random ordering without PostgreSQL ORDER BY RANDOM() full scan.

    Same user sees a stable order across requests; different users see different orderings.
    """
    viewer_key = str(viewer_user_id)
    return queryset.annotate(
        _discover_key=MD5(
            Concat(
                Cast("id", output_field=CharField()),
                Cast(viewer_key, output_field=CharField()),
                output_field=CharField(),
            )
        )
    ).order_by("_discover_key")


def conversation_list_queryset(user, *, show_archived: bool, unread_only: bool):
    """Optimized conversation inbox queryset with annotations and prefetches."""
    last_message_id = (
        Message.objects.filter(conversation=OuterRef("pk"))
        .order_by("-timestamp", "-id")
        .values("id")[:1]
    )

    convos = (
        Conversation.objects.filter(Q(match__user1=user) | Q(match__user2=user))
        .select_related(
            "match",
            "match__user1",
            "match__user1__profile",
            "match__user2",
            "match__user2__profile",
        )
        .prefetch_related(
            Prefetch(
                "preferences",
                queryset=ConversationPreference.objects.filter(user=user),
                to_attr="user_preferences",
            )
        )
        .annotate(
            unread_count_annotated=Count(
                "messages",
                filter=Q(messages__is_read=False) & ~Q(messages__sender=user),
            ),
            last_message_id=Subquery(last_message_id),
            pinned_for_user=Exists(
                ConversationPreference.objects.filter(
                    conversation=OuterRef("pk"),
                    user=user,
                    is_pinned=True,
                )
            ),
        )
    )

    if not show_archived:
        convos = convos.exclude(
            preferences__user=user,
            preferences__is_archived=True,
        )

    if unread_only:
        convos = convos.filter(unread_count_annotated__gt=0)

    return convos.order_by("-pinned_for_user", "-last_message_at", "-created_at")


def prefetch_conversation_last_messages(conversations) -> dict[int, Message]:
    """Batch-load last messages for a conversation list (one query)."""
    message_ids = [
        convo.last_message_id
        for convo in conversations
        if getattr(convo, "last_message_id", None)
    ]
    if not message_ids:
        return {}

    messages = (
        Message.objects.filter(id__in=message_ids)
        .select_related("sender__profile", "reply_to", "reply_to__sender__profile")
        .prefetch_related("reactions", "deleted_by")
    )
    return {message.id: message for message in messages}
