from django.utils import timezone
from rest_framework import serializers
from .models import Conversation, Message
from .services import build_reactions_summary
from accounts.serializers import ProfileSerializer


class ReplyPreviewSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    content = serializers.CharField()
    sender_name = serializers.CharField()
    image_url = serializers.CharField(allow_blank=True)
    message_type = serializers.CharField()


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.profile.full_name', read_only=True)
    sender_photo = serializers.CharField(source='sender.profile.photo_url', read_only=True)
    sender_id = serializers.IntegerField(source='sender.id', read_only=True)
    is_mine = serializers.SerializerMethodField()
    reactions = serializers.SerializerMethodField()
    is_deleted_for_me = serializers.SerializerMethodField()
    reply_to = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            'id',
            'content',
            'image_url',
            'message_type',
            'timestamp',
            'delivered_at',
            'read_at',
            'edited_at',
            'is_read',
            'sender_id',
            'sender_name',
            'sender_photo',
            'is_mine',
            'reactions',
            'reply_to',
            'is_deleted_for_everyone',
            'is_deleted_for_me',
        ]

    def get_reactions(self, obj):
        return build_reactions_summary(obj)

    def get_is_mine(self, obj):
        request = self.context.get('request')
        return request and obj.sender == request.user

    def get_is_deleted_for_me(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.deleted_by.filter(id=request.user.id).exists()
        return False

    def get_reply_to(self, obj):
        parent = obj.reply_to
        if not parent or parent.is_deleted_for_everyone:
            return None
        return {
            'id': parent.id,
            'content': parent.content,
            'sender_name': getattr(parent.sender.profile, 'full_name', '') or parent.sender.username,
            'image_url': parent.image_url or '',
            'message_type': parent.message_type,
        }

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if instance.is_deleted_for_everyone:
            ret['content'] = "This message was deleted"
            ret['image_url'] = ""
        return ret


class ConversationSerializer(serializers.ModelSerializer):
    other_user_profile = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    match_id = serializers.IntegerField(source='match.id', read_only=True)
    match_created_at = serializers.DateTimeField(source='match.matched_at', read_only=True)
    other_user_nickname = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    is_other_user_typing = serializers.SerializerMethodField()
    is_archived = serializers.SerializerMethodField()
    is_muted = serializers.SerializerMethodField()
    is_pinned = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            'id',
            'public_id',
            'match_id',
            'match_created_at',
            'other_user_profile',
            'other_user_nickname',
            'last_message',
            'last_message_at',
            'created_at',
            'is_other_user_typing',
            'unread_count',
            'is_archived',
            'is_muted',
            'is_pinned',
        ]

    def get_other_user_profile(self, obj):
        request_user = self.context.get('request').user
        other_user = obj.match.get_other_user(request_user)
        return ProfileSerializer(other_user.profile).data

    def get_other_user_nickname(self, obj):
        request_user = self.context.get('request').user
        pref = obj.preferences.filter(user=request_user).first()
        return pref.nickname if pref else ''

    def get_last_message(self, obj):
        msg = obj.messages.order_by('-timestamp', '-id').first()
        if msg:
            return MessageSerializer(msg, context=self.context).data
        return None

    def get_is_other_user_typing(self, obj):
        request_user = self.context.get('request').user
        is_user1 = (obj.match.user1 == request_user)

        last_typed = obj.user2_last_typed if is_user1 else obj.user1_last_typed

        if last_typed:
            return (timezone.now() - last_typed).total_seconds() < 5
        return False

    def get_unread_count(self, obj):
        annotated = getattr(obj, "unread_count_annotated", None)
        if annotated is not None:
            return int(annotated)

        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return 0

        return (
            obj.messages.filter(is_read=False)
            .exclude(sender=request.user)
            .count()
        )

    def _get_user_pref(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        return obj.preferences.filter(user=request.user).first()

    def get_is_archived(self, obj):
        pref = self._get_user_pref(obj)
        return bool(pref and pref.is_archived)

    def get_is_muted(self, obj):
        pref = self._get_user_pref(obj)
        return bool(pref and pref.is_muted)

    def get_is_pinned(self, obj):
        pref = self._get_user_pref(obj)
        return bool(pref and pref.is_pinned)


class SendMessageSerializer(serializers.Serializer):
    content = serializers.CharField(required=False, allow_blank=True, default='')
    image_url = serializers.CharField(required=False, allow_blank=True, default='')
    reply_to_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_reply_to_id(self, value):
        if value is None:
            return value
        convo = self.context.get('conversation')
        if not convo:
            return value
        if not convo.messages.filter(id=value).exists():
            raise serializers.ValidationError('Reply target not found in this conversation.')
        return value
