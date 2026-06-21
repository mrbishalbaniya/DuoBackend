from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Profile

User = get_user_model()


class ProfileSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    profile_completeness = serializers.IntegerField(read_only=True)

    class Meta:
        model = Profile
        fields = [
            "id",
            "user_id",
            "username",
            "email",
            "full_name",
            "phone_country_code",
            "phone_number",
            "age",
            "gender",
            "location",
            "bio",
            "religion",
            "education",
            "occupation",
            "work_preference",
            "lifestyle_tags",
            "photo_url",
            "photo_urls",
            "pref_age_min",
            "pref_age_max",
            "pref_min_height",
            "pref_occupation",
            "pref_values",
            "pref_gender",
            "pref_location",
            "pref_max_distance_km",
            "pref_relationship_goal",
            "pref_verified_only",
            "relationship_goal",
            "is_verified",
            "is_onboarded",
            "profile_completeness",
        ]
        read_only_fields = ["id", "user_id", "username", "email", "profile_completeness"]


class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "profile"]


class GoogleAuthSerializer(serializers.Serializer):
    id_token = serializers.CharField()


class EmailOtpSendSerializer(serializers.Serializer):
    email = serializers.EmailField()


class EmailOtpVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(min_length=6, max_length=6)


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    full_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    username = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ["username", "email", "password", "full_name"]

    def create(self, validated_data):
        full_name = validated_data.pop("full_name", "")
        username = (validated_data.pop("username", None) or "").strip()
        email = validated_data["email"]

        if not username:
            username = email

        base_username = username
        suffix = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{suffix}"
            suffix += 1

        user = User.objects.create_user(
            username=username,
            email=email,
            password=validated_data["password"],
        )
        profile, _ = Profile.objects.get_or_create(user=user)
        if full_name:
            profile.full_name = full_name
            profile.save(update_fields=["full_name", "updated_at"])
        return user
