from django.utils import timezone
from django.core.signing import TimestampSigner
from rest_framework import status, parsers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q
from duo_project.cloudinary_upload import CloudinaryNotConfiguredError, upload_chat_media
from drf_spectacular.utils import OpenApiResponse, extend_schema
from matching.models import Swipe

from .models import Conversation, ConversationPreference, Message, UserBlock, UserReport
from .realtime import broadcast_chat_message, broadcast_typing_status
from .serializers import ConversationSerializer, MessageSerializer, SendMessageSerializer


def get_user_conversation(conversation_id, user):
    try:
        convo = Conversation.objects.select_related(
            'match',
            'match__user1',
            'match__user2',
        ).get(id=conversation_id)
    except Conversation.DoesNotExist:
        return None, Response({'detail': 'Conversation not found.'}, status=status.HTTP_404_NOT_FOUND)

    match = convo.match
    if user not in (match.user1, match.user2):
        return None, Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

    return convo, None


class ConversationListView(APIView):
    """List all conversations for the current user."""

    @extend_schema(
        tags=["Chat"],
        summary="List my conversations",
        responses={200: ConversationSerializer(many=True)},
    )
    def get(self, request):
        convos = Conversation.objects.filter(
            Q(match__user1=request.user) | Q(match__user2=request.user)
        ).order_by('-created_at')
        serializer = ConversationSerializer(convos, many=True, context={'request': request})
        return Response(serializer.data)


class MessageListView(APIView):
    """Get/send messages in a conversation."""

    @extend_schema(
        tags=["Chat"],
        summary="List messages in a conversation",
        responses={200: MessageSerializer(many=True)},
    )
    def get(self, request, conversation_id):
        try:
            convo = Conversation.objects.get(
                id=conversation_id
            )
        except Conversation.DoesNotExist:
            return Response({'error': 'Conversation not found'}, status=404)

        # Verify user is part of this conversation
        match = convo.match
        if request.user not in [match.user1, match.user2]:
            return Response({'error': 'Forbidden'}, status=403)

        # Mark messages as read
        convo.messages.exclude(sender=request.user).update(is_read=True)

        messages = convo.messages.all()
        serializer = MessageSerializer(messages, many=True, context={'request': request})
        return Response(serializer.data)

    @extend_schema(
        tags=["Chat"],
        summary="Send a message",
        request=SendMessageSerializer,
        responses={201: MessageSerializer},
    )
    def post(self, request, conversation_id):
        try:
            convo = Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            return Response({'error': 'Conversation not found'}, status=404)

        match = convo.match
        if request.user not in [match.user1, match.user2]:
            return Response({'error': 'Forbidden'}, status=403)

        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        msg = Message.objects.create(
            conversation=convo,
            sender=request.user,
            content=serializer.validated_data.get('content', ''),
            image_url=serializer.validated_data.get('image_url', ''),
        )

        profile = getattr(request.user, "profile", None)
        sender_name = (getattr(profile, "full_name", None) or "").strip() or request.user.username
        broadcast_chat_message(
            convo.id,
            msg_id=msg.id,
            content=msg.content,
            image_url=msg.image_url,
            sender_id=request.user.id,
            sender_name=sender_name,
            timestamp=msg.timestamp.isoformat(),
        )

        from notifications.dispatch import dispatch_chat_message_push

        dispatch_chat_message_push(msg)

        return Response(
            MessageSerializer(msg, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )


class ConversationDetailView(APIView):
    """Get a single conversation's details."""

    @extend_schema(
        tags=["Chat"],
        summary="Get conversation details",
        responses={200: ConversationSerializer},
    )
    def get(self, request, conversation_id):
        try:
            convo = Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            return Response({'error': 'Conversation not found'}, status=404)

        match = convo.match
        if request.user not in [match.user1, match.user2]:
            return Response({'error': 'Forbidden'}, status=403)

        return Response(ConversationSerializer(convo, context={'request': request}).data)


class TypingHeartbeatView(APIView):
    """Mark the current user as typing in this conversation."""

    @extend_schema(
        tags=["Chat"],
        summary="Send typing heartbeat",
        responses={200: OpenApiResponse(description="Typing timestamp updated.")},
    )
    def post(self, request, conversation_id):
        try:
            convo = Conversation.objects.get(id=conversation_id)
        except Conversation.DoesNotExist:
            return Response({'error': 'Conversation not found'}, status=404)

        match = convo.match
        if request.user not in [match.user1, match.user2]:
            return Response({'error': 'Forbidden'}, status=403)

        if match.user1 == request.user:
            convo.user1_last_typed = timezone.now()
        else:
            convo.user2_last_typed = timezone.now()
        
        convo.save(update_fields=['user1_last_typed', 'user2_last_typed'])
        broadcast_typing_status(convo.id, user_id=request.user.id, is_typing=True)
        return Response({'status': 'ok'})

class ImageUploadView(APIView):
    """Upload an image for chat."""
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

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
            file_url = upload_chat_media(image, user_id=request.user.id)
        except CloudinaryNotConfiguredError as exc:
            return Response({'detail': str(exc)}, status=503)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)

        return Response({'image_url': file_url}, status=201)


class ConversationSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Chat"],
        summary="Update conversation settings (nickname)",
    )
    def patch(self, request, conversation_id):
        convo, error = get_user_conversation(conversation_id, request.user)
        if error:
            return error

        nickname = str(request.data.get('nickname', '')).strip()[:64]
        pref, _ = ConversationPreference.objects.get_or_create(
            user=request.user,
            conversation=convo,
        )
        pref.nickname = nickname
        pref.save(update_fields=['nickname', 'updated_at'])

        return Response({'nickname': pref.nickname})


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

        for message in convo.messages.all():
            message.deleted_by.add(request.user)

        return Response({'detail': 'Chat history cleared.'})


class ConversationUnmatchView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Chat"],
        summary="Unmatch and block the other user",
    )
    def post(self, request, conversation_id):
        convo, error = get_user_conversation(conversation_id, request.user)
        if error:
            return error

        other_user = convo.match.get_other_user(request.user)
        UserBlock.objects.get_or_create(blocker=request.user, blocked=other_user)
        Swipe.objects.update_or_create(
            from_user=request.user,
            to_user=other_user,
            defaults={'action': 'SKIP'},
        )
        Swipe.objects.update_or_create(
            from_user=other_user,
            to_user=request.user,
            defaults={'action': 'SKIP'},
        )
        convo.match.delete()

        return Response({'detail': 'Unmatched and blocked successfully.'})


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
        ticket = signer.sign(f"{request.user.id}:{convo.id}")
        return Response({"ticket": ticket})
