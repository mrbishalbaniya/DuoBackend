from django.utils import timezone
from django.core.signing import TimestampSigner
from rest_framework import status, parsers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q
from duo_project.query_optimization import (
    apply_list_window,
    conversation_list_queryset,
    prefetch_conversation_last_messages,
)
from accounts.throttling import AuthRateThrottle, UploadRateThrottle
from duo_project.cloudinary_media.responses import upload_response_dict
from duo_project.cloudinary_upload import CloudinaryNotConfiguredError, upload_chat_media_result
from drf_spectacular.utils import OpenApiResponse, extend_schema
from matching.models import Match, Swipe
from accounts.serializer_context import profile_list_serializer_context
from duo_project.cache.invalidation import invalidate_match_users, invalidate_user_caches
from duo_project.cache import api_cache, get_user_cache_version
from duo_project.cache import keys as cache_keys
from duo_project.cache import ttl as cache_ttl
from duo_project.cache.presence import set_typing

from .models import Conversation, ConversationPreference, Message, UserBlock, UserReport
from .realtime import (
    broadcast_chat_message,
    broadcast_message_deleted,
    broadcast_message_reacted,
    broadcast_messages_read,
    broadcast_typing_status,
)
from .serializers import (
    ConversationSerializer,
    MessageSerializer,
    SecurityEventSerializer,
    SendMessageSerializer,
)
from .services import (
    conversation_is_blocked,
    create_security_system_message,
    delete_message_for_user,
    ensure_conversations_for_user,
    infer_message_type,
    mark_messages_delivered,
    mark_messages_read,
    react_to_message,
    sanitize_message_content,
    touch_conversation_activity,
)


def resolve_conversation(lookup):
    """Resolve by 10-digit public_id, with legacy autoincrement id fallback."""
    qs = Conversation.objects.select_related(
        "match",
        "match__user1",
        "match__user2",
    )
    key = str(lookup).strip()
    convo = qs.filter(public_id=key).first()
    if convo:
        return convo
    if key.isdigit() and len(key) < 10:
        return qs.filter(id=int(key)).first()
    return None


def get_user_conversation(conversation_id, user):
    convo = resolve_conversation(conversation_id)
    if convo is None:
        return None, Response({'detail': 'Conversation not found.'}, status=status.HTTP_404_NOT_FOUND)

    match = convo.match
    if user not in (match.user1, match.user2):
        return None, Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

    if conversation_is_blocked(convo, user):
        return None, Response({'detail': 'This conversation is unavailable.'}, status=status.HTTP_403_FORBIDDEN)

    return convo, None


def _conversation_other_user(convo, user):
    return convo.match.get_other_user(user)


def _set_mutual_swipes_to_skip(user, other_user):
    Swipe.objects.update_or_create(
        from_user=user,
        to_user=other_user,
        defaults={"action": "SKIP"},
    )
    Swipe.objects.update_or_create(
        from_user=other_user,
        to_user=user,
        defaults={"action": "SKIP"},
    )


def _delete_match_and_invalidate(convo, user, other_user):
    convo.match.delete()
    invalidate_match_users(user.id, other_user.id, reason="unmatch")


class ConversationListView(APIView):
    """List all conversations for the current user."""

    @extend_schema(
        tags=["Chat"],
        summary="List my conversations",
        responses={200: ConversationSerializer(many=True)},
    )
    def get(self, request):
        created = ensure_conversations_for_user(request.user)
        if created:
            invalidate_user_caches(request.user.id, reason="conversation_repair")

        show_archived = request.query_params.get('archived') == 'true'
        unread_only = request.query_params.get('unread') == 'true'
        version = get_user_cache_version(request.user.id)
        limit, offset = cache_keys.list_window_suffix(request)
        cache_key = cache_keys.conversations(
            request.user.id,
            version,
            archived=show_archived,
            unread=unread_only,
            limit=limit,
            offset=offset,
        )

        def build():
            convos = conversation_list_queryset(
                request.user,
                show_archived=show_archived,
                unread_only=unread_only,
            )
            convos = apply_list_window(
                convos,
                request,
                default_limit=200,
                max_limit=500,
            )
            convo_list = list(convos)
            last_messages = prefetch_conversation_last_messages(convo_list)
            profiles = []
            for convo in convo_list:
                profiles.append(convo.match.get_other_user(request.user).profile)

            return ConversationSerializer(
                convo_list,
                many=True,
                context={
                    **profile_list_serializer_context(request, profiles),
                    "last_messages": last_messages,
                },
            ).data

        return Response(
            api_cache.get_or_set(
                cache_key,
                build,
                cache_ttl.CONVERSATIONS,
                label="conversations",
            )
        )


class MessageListView(APIView):
    """Get/send messages in a conversation."""

    @extend_schema(
        tags=["Chat"],
        summary="List messages in a conversation",
        responses={200: MessageSerializer(many=True)},
    )
    def get(self, request, conversation_id):
        convo, error = get_user_conversation(conversation_id, request.user)
        if error:
            return error

        limit = min(int(request.query_params.get('limit', 50)), 100)
        before = request.query_params.get('before')

        qs = convo.messages.select_related(
            'sender__profile',
            'reply_to',
            'reply_to__sender__profile',
        ).prefetch_related('reactions', 'deleted_by')

        if before:
            try:
                before_id = int(before)
                qs = qs.filter(id__lt=before_id)
            except (TypeError, ValueError):
                pass

        messages = list(qs.order_by('-timestamp', '-id')[:limit])
        messages.reverse()

        read_ids = mark_messages_read(convo, request.user)
        if read_ids:
            broadcast_messages_read(
                convo.public_id,
                reader_id=request.user.id,
                message_ids=read_ids,
            )

        mark_messages_delivered(convo, request.user)

        serializer = MessageSerializer(messages, many=True, context={'request': request})
        payload = serializer.data
        has_more = len(messages) == limit
        return Response({
            'results': payload,
            'has_more': has_more,
            'next_before': payload[0]['id'] if has_more and payload else None,
        })

    @extend_schema(
        tags=["Chat"],
        summary="Send a message",
        request=SendMessageSerializer,
        responses={201: MessageSerializer},
    )
    def post(self, request, conversation_id):
        convo, error = get_user_conversation(conversation_id, request.user)
        if error:
            return error

        serializer = SendMessageSerializer(
            data=request.data,
            context={'conversation': convo},
        )
        serializer.is_valid(raise_exception=True)

        content = sanitize_message_content(serializer.validated_data.get('content', ''))
        image_url = serializer.validated_data.get('image_url', '')
        reply_to_id = serializer.validated_data.get('reply_to_id')

        reply_to = None
        if reply_to_id:
            reply_to = convo.messages.filter(id=reply_to_id).first()

        msg = Message.objects.create(
            conversation=convo,
            sender=request.user,
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
            .prefetch_related('reactions')
            .get(id=msg.id)
        )

        profile = getattr(request.user, "profile", None)
        sender_name = (getattr(profile, "full_name", None) or "").strip() or request.user.username
        broadcast_chat_message(
            convo.public_id,
            msg_id=msg.id,
            content=msg.content,
            image_url=msg.image_url,
            sender_id=request.user.id,
            sender_name=sender_name,
            timestamp=msg.timestamp.isoformat(),
            message_type=msg.message_type,
            reply_to=MessageSerializer(msg, context={'request': request}).data.get('reply_to'),
        )

        from notifications.dispatch import dispatch_chat_message_push

        dispatch_chat_message_push(msg)

        return Response(
            MessageSerializer(msg, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )


class MessageDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Chat"], summary="Delete a message")
    def post(self, request, message_id):
        delete_type = str(request.data.get('delete_type', 'for_me')).strip()
        if delete_type not in ('for_me', 'for_everyone'):
            return Response({'detail': 'Invalid delete_type.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            msg = Message.objects.select_related('conversation__match').get(id=message_id)
        except Message.DoesNotExist:
            return Response({'detail': 'Message not found.'}, status=status.HTTP_404_NOT_FOUND)

        convo = msg.conversation
        _, error = get_user_conversation(convo.public_id, request.user)
        if error:
            return error

        if not delete_message_for_user(msg, request.user, delete_type):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        broadcast_message_deleted(
            convo.public_id,
            message_id=msg.id,
            user_id=request.user.id,
            delete_type=delete_type,
        )
        return Response({'detail': 'Message deleted.'})


class MessageReactView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Chat"], summary="React to a message")
    def post(self, request, message_id):
        emoji = str(request.data.get('emoji', '')).strip()
        if not emoji:
            return Response({'detail': 'Emoji is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            msg = Message.objects.select_related('conversation__match').prefetch_related('reactions').get(id=message_id)
        except Message.DoesNotExist:
            return Response({'detail': 'Message not found.'}, status=status.HTTP_404_NOT_FOUND)

        convo = msg.conversation
        convo_check, error = get_user_conversation(convo.public_id, request.user)
        if error:
            return error

        reactions = react_to_message(msg, request.user, emoji)
        broadcast_message_reacted(
            convo.public_id,
            message_id=msg.id,
            user_id=request.user.id,
            emoji=emoji,
            reactions=reactions,
        )
        from notifications.dispatch import dispatch_message_reaction_push

        dispatch_message_reaction_push(message=msg, reactor=request.user, emoji=emoji)
        return Response(MessageSerializer(msg, context={'request': request}).data)


class ConversationDetailView(APIView):
    """Get a single conversation's details."""

    @extend_schema(
        tags=["Chat"],
        summary="Get conversation details",
        responses={200: ConversationSerializer},
    )
    def get(self, request, conversation_id):
        convo, error = get_user_conversation(conversation_id, request.user)
        if error:
            return error

        return Response(ConversationSerializer(convo, context={'request': request}).data)


class TypingHeartbeatView(APIView):
    """Mark the current user as typing in this conversation."""

    @extend_schema(
        tags=["Chat"],
        summary="Send typing heartbeat",
        responses={200: OpenApiResponse(description="Typing timestamp updated.")},
    )
    def post(self, request, conversation_id):
        convo, error = get_user_conversation(conversation_id, request.user)
        if error:
            return error

        match = convo.match
        if match.user1 == request.user:
            convo.user1_last_typed = timezone.now()
        else:
            convo.user2_last_typed = timezone.now()

        convo.save(update_fields=['user1_last_typed', 'user2_last_typed'])
        set_typing(convo.public_id, request.user.id)
        broadcast_typing_status(convo.public_id, user_id=request.user.id, is_typing=True)
        return Response({'status': 'ok'})


class ImageUploadView(APIView):
    """Upload an image for chat."""
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]
    throttle_classes = [UploadRateThrottle]

    @extend_schema(
        tags=["Chat"],
        summary="Upload a chat image",
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {"image": {"type": "string", "format": "binary"}},
                "required": ["image"],
            }
        },
        responses={201: OpenApiResponse(description="Returns uploaded image URL.")},
    )
    def post(self, request):
        if 'image' not in request.data:
            return Response({'error': 'No image provided'}, status=400)

        image = request.data['image']

        try:
            upload_result = upload_chat_media_result(image, user_id=request.user.id)
        except CloudinaryNotConfiguredError as exc:
            return Response({'detail': str(exc)}, status=503)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)

        return Response(upload_response_dict(upload_result), status=201)


class ConversationSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Chat"],
        summary="Update conversation settings",
    )
    def patch(self, request, conversation_id):
        convo, error = get_user_conversation(conversation_id, request.user)
        if error:
            return error

        pref, _ = ConversationPreference.objects.get_or_create(
            user=request.user,
            conversation=convo,
        )

        update_fields = ['updated_at']
        if 'nickname' in request.data:
            pref.nickname = str(request.data.get('nickname', '')).strip()[:64]
            update_fields.append('nickname')
        if 'is_archived' in request.data:
            pref.is_archived = bool(request.data.get('is_archived'))
            update_fields.append('is_archived')
        if 'is_muted' in request.data:
            pref.is_muted = bool(request.data.get('is_muted'))
            update_fields.append('is_muted')
        if 'is_pinned' in request.data:
            pref.is_pinned = bool(request.data.get('is_pinned'))
            update_fields.append('is_pinned')
        if 'notify_screenshots' in request.data:
            pref.notify_screenshots = bool(request.data.get('notify_screenshots'))
            update_fields.append('notify_screenshots')
        if 'secure_chat' in request.data:
            pref.secure_chat = bool(request.data.get('secure_chat'))
            update_fields.append('secure_chat')

        pref.save(update_fields=update_fields)

        return Response({
            'nickname': pref.nickname,
            'is_archived': pref.is_archived,
            'is_muted': pref.is_muted,
            'is_pinned': pref.is_pinned,
            'notify_screenshots': pref.notify_screenshots,
            'secure_chat': pref.secure_chat,
        })


class ConversationSecurityEventView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Chat"],
        summary="Report a screenshot or screen recording event",
        request=SecurityEventSerializer,
        responses={201: MessageSerializer},
    )
    def post(self, request, conversation_id):
        convo, error = get_user_conversation(conversation_id, request.user)
        if error:
            return error

        serializer = SecurityEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event_code = serializer.validated_data["event_code"]

        msg = create_security_system_message(convo, request.user, event_code)
        if not msg:
            return Response(
                {'detail': 'Security event was not recorded.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        msg = (
            Message.objects.select_related(
                "sender__profile",
                "conversation__match",
                "reply_to",
                "reply_to__sender__profile",
            )
            .prefetch_related('reactions')
            .get(id=msg.id)
        )

        profile = getattr(request.user, "profile", None)
        sender_name = (getattr(profile, "full_name", None) or "").strip() or request.user.username
        broadcast_chat_message(
            convo.public_id,
            msg_id=msg.id,
            content=msg.content,
            image_url="",
            sender_id=request.user.id,
            sender_name=sender_name,
            timestamp=msg.timestamp.isoformat(),
            message_type=msg.message_type,
            event_code=msg.event_code,
        )

        return Response(
            MessageSerializer(msg, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class ConversationClearHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Chat"],
        summary="Clear chat history for the current user",
    )
    def post(self, request, conversation_id):
        convo, error = get_user_conversation(conversation_id, request.user)
        if error:
            return error

        through_model = Message.deleted_by.through
        message_ids = list(convo.messages.values_list("id", flat=True))
        if message_ids:
            existing = set(
                through_model.objects.filter(
                    message_id__in=message_ids,
                    user_id=request.user.id,
                ).values_list("message_id", flat=True)
            )
            through_model.objects.bulk_create(
                [
                    through_model(message_id=mid, user_id=request.user.id)
                    for mid in message_ids
                    if mid not in existing
                ],
                ignore_conflicts=True,
            )

        return Response({'detail': 'Chat history cleared.'})


class ConversationUnmatchView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Chat"],
        summary="Unmatch the other user",
    )
    def post(self, request, conversation_id):
        convo, error = get_user_conversation(conversation_id, request.user)
        if error:
            return error

        other_user = _conversation_other_user(convo, request.user)
        _set_mutual_swipes_to_skip(request.user, other_user)
        _delete_match_and_invalidate(convo, request.user, other_user)

        return Response({"detail": "Unmatched successfully."})


class ConversationBlockView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Chat"],
        summary="Block the other user",
    )
    def post(self, request, conversation_id):
        convo, error = get_user_conversation(conversation_id, request.user)
        if error:
            return error

        other_user = _conversation_other_user(convo, request.user)
        UserBlock.objects.get_or_create(blocker=request.user, blocked=other_user)
        invalidate_user_caches(request.user.id, reason="block")
        invalidate_user_caches(other_user.id, reason="block")

        return Response({"detail": "User blocked successfully."})


class ConversationUnmatchBlockView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Chat"],
        summary="Unmatch and block the other user",
    )
    def post(self, request, conversation_id):
        convo, error = get_user_conversation(conversation_id, request.user)
        if error:
            return error

        other_user = _conversation_other_user(convo, request.user)
        UserBlock.objects.get_or_create(blocker=request.user, blocked=other_user)
        _set_mutual_swipes_to_skip(request.user, other_user)
        _delete_match_and_invalidate(convo, request.user, other_user)

        return Response({"detail": "Unmatched and blocked successfully."})


class ConversationReportView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Chat"],
        summary="Report the other user in this conversation",
    )
    def post(self, request, conversation_id):
        convo, error = get_user_conversation(conversation_id, request.user)
        if error:
            return error

        other_user = convo.match.get_other_user(request.user)
        reason = str(request.data.get('reason', '')).strip()

        UserReport.objects.create(
            reporter=request.user,
            reported=other_user,
            conversation=convo,
            reason=reason,
        )

        return Response({'detail': 'Report submitted. Our team will review it.'})


class WebSocketTicketView(APIView):
    """Issue a short-lived signed ticket for WebSocket authentication."""

    @extend_schema(
        tags=["Chat"],
        summary="Get WebSocket connection ticket",
        responses={200: OpenApiResponse(description='{"ticket": "..."}')},
    )
    def post(self, request, conversation_id):
        convo, error = get_user_conversation(conversation_id, request.user)
        if error:
            return error

        signer = TimestampSigner(salt="duo-ws-ticket")
        ticket = signer.sign(f"{request.user.id}:{convo.public_id}")
        return Response({"ticket": ticket})
