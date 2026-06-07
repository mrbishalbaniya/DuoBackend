from django.utils import timezone
from rest_framework import serializers
from .models import Conversation, Message
from accounts.serializers import ProfileSerializer


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.profile.full_name', read_only=True)
    sender_photo = serializers.CharField(source='sender.profile.photo_url', read_only=True)
    is_mine = serializers.SerializerMethodField()
    reactions = serializers.SerializerMethodField()
    is_deleted_for_me = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ['id', 'content', 'image_url', 'timestamp', 'is_read',
                  'sender_name', 'sender_photo', 'is_mine', 'reactions',
                  'is_deleted_for_everyone', 'is_deleted_for_me']

    def get_reactions(self, obj):
        # Return summary of reactions: emoji -> count
        reactions = obj.reactions.all()
        summary = {}
        for r in reactions:
            summary[r.emoji] = summary.get(r.emoji, 0) + 1
        return summary

    def get_is_mine(self, obj):
        request = self.context.get('request')
        return request and obj.sender == request.user

    def get_is_deleted_for_me(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.deleted_by.filter(id=request.user.id).exists()
        return False
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

    is_other_user_typing = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ['id', 'match_id', 'other_user_profile', 'last_message', 'created_at', 'is_other_user_typing']

    def get_other_user_profile(self, obj):
        request_user = self.context.get('request').user
        other_user = obj.match.get_other_user(request_user)
        return ProfileSerializer(other_user.profile).data

    def get_last_message(self, obj):
        msg = obj.messages.last()
        if msg:
            return MessageSerializer(msg, context=self.context).data
        return None

    def get_is_other_user_typing(self, obj):
        request_user = self.context.get('request').user
        is_user1 = (obj.match.user1 == request_user)
        
        # Check the OTHER user's last typed timestamp
        last_typed = obj.user2_last_typed if is_user1 else obj.user1_last_typed
        
        if last_typed:
            # Active if typed within the last 5 seconds
            return (timezone.now() - last_typed).total_seconds() < 5
        return False


class SendMessageSerializer(serializers.Serializer):
    content = serializers.CharField(required=False, allow_blank=True, default='')
    image_url = serializers.CharField(required=False, allow_blank=True, default='')
