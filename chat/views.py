from django.utils import timezone
from rest_framework import status, parsers
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q
from django.core.files.storage import default_storage
from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, extend_schema
from .models import Conversation, Message
from .serializers import ConversationSerializer, MessageSerializer, SendMessageSerializer


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
        
        # Save file
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"chat_{timestamp}_{image.name}"
        file_path = f"chat_images/{filename}"
        
        saved_path = default_storage.save(file_path, image)
        file_url = request.build_absolute_uri(f"{settings.MEDIA_URL}{saved_path}")
        
        return Response({'image_url': file_url}, status=201)
