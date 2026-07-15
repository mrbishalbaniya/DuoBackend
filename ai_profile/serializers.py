from rest_framework import serializers


class ProfileGenerateRequestSerializer(serializers.Serializer):
    style = serializers.ChoiceField(
        choices=[
            "professional",
            "romantic",
            "funny",
            "minimal",
            "confident",
            "adventurous",
            "intellectual",
            "friendly",
        ],
        required=False,
        default="friendly",
    )
    language = serializers.ChoiceField(
        choices=["en", "ne", "hi"],
        required=False,
        default="en",
    )
    force = serializers.BooleanField(required=False, default=False)
    apply = serializers.BooleanField(
        required=False,
        default=False,
        help_text="When true, write bio onto the user profile and stash goals into pref_values.",
    )


class ProfileGenerateResponseSerializer(serializers.Serializer):
    bio = serializers.CharField()
    future_goals = serializers.CharField()
    looking_for = serializers.CharField()
    traits = serializers.ListField(child=serializers.CharField(), required=False)
    style = serializers.CharField(required=False)
    language = serializers.CharField(required=False)
    cached = serializers.BooleanField(required=False)
