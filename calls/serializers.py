from rest_framework import serializers

from calls.models import CallSession


class InitiateCallSerializer(serializers.Serializer):
    conversation_id = serializers.CharField(max_length=32)
    call_type = serializers.ChoiceField(choices=[CallSession.TYPE_VOICE, CallSession.TYPE_VIDEO])


class CallSessionSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="public_id", read_only=True)
    conversation_id = serializers.CharField(source="conversation.public_id", read_only=True)
    caller_id = serializers.IntegerField(read_only=True)
    callee_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = CallSession
        fields = [
            "id",
            "conversation_id",
            "call_type",
            "status",
            "caller_id",
            "callee_id",
            "started_at",
            "answered_at",
            "ended_at",
            "duration_seconds",
            "end_reason",
        ]
