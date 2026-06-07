from rest_framework import serializers
from .models import Swipe, Match
from accounts.serializers import ProfileSerializer


class SwipeSerializer(serializers.Serializer):
    to_user_id = serializers.IntegerField()
    action = serializers.ChoiceField(choices=['LIKE', 'SKIP', 'SUPERLIKE'])


class MatchSerializer(serializers.ModelSerializer):
    other_user_profile = serializers.SerializerMethodField()

    class Meta:
        model = Match
        fields = [
            'id', 'compatibility_score', 'matched_at', 'other_user_profile',
            'values_score', 'lifestyle_score', 'career_score', 'hobbies_score',
            'spark_factors', 'shared_interests', 'vision_insight', 'communication_insight',
        ]

    def get_other_user_profile(self, obj):
        request_user = self.context.get('request').user
        other_user = obj.get_other_user(request_user)
        return ProfileSerializer(other_user.profile).data
