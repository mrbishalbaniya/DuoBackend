from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Profile
from subscriptions.services import get_active_subscription, user_has_active_subscription
from subscriptions.wallet_services import get_wallet_balance

User = get_user_model()

LOCATION_PRIVACY_FIELDS = (
    "location_ghost_mode",
    "location_visibility",
    "location_visibility_friends",
)


class ProfileSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    profile_completeness = serializers.IntegerField(read_only=True)
    is_premium = serializers.SerializerMethodField()
    subscription_expires_at = serializers.SerializerMethodField()
    wallet_balance = serializers.SerializerMethodField()

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
            "location_ghost_mode",
            "location_visibility",
            "location_visibility_friends",
            "is_verified",
            "is_onboarded",
            "profile_completeness",
            "is_premium",
            "subscription_expires_at",
            "wallet_balance",
        ]
        read_only_fields = [
            "id",
            "user_id",
            "username",
            "email",
            "profile_completeness",
            "is_verified",
            "is_premium",
            "subscription_expires_at",
            "wallet_balance",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        viewer = getattr(request, "user", None) if request else None
        owner_id = getattr(instance, "user_id", None) or getattr(
            getattr(instance, "user", None), "id", None
        )
        is_owner = (
            viewer is not None
            and getattr(viewer, "is_authenticated", False)
            and owner_id is not None
            and int(viewer.id) == int(owner_id)
        )
        if not is_owner:
            for field in LOCATION_PRIVACY_FIELDS:
                data.pop(field, None)
            data.pop("wallet_balance", None)
            data["email"] = ""
            data["phone_country_code"] = ""
            data["phone_number"] = ""
            if viewer is not None and not instance.is_location_visible_to(viewer):
                data["location"] = ""
        return data

    def get_is_premium(self, obj):
        billing = self.context.get("profile_billing")
        if billing is not None:
            entry = billing.get(obj.user_id)
            if entry is not None:
                return bool(entry.get("is_premium"))
        return user_has_active_subscription(obj.user)

    def get_subscription_expires_at(self, obj):
        billing = self.context.get("profile_billing")
        if billing is not None:
            entry = billing.get(obj.user_id)
            if entry is not None:
                return entry.get("subscription_expires_at")
        active = get_active_subscription(obj.user)
        return active.expires_at if active else None

    def get_wallet_balance(self, obj):
        billing = self.context.get("profile_billing")
        if billing is not None:
            entry = billing.get(obj.user_id)
            if entry is not None:
                return int(entry.get("wallet_balance", 0))
        return int(get_wallet_balance(obj.user))

    def validate_location_visibility(self, value):
        allowed = {choice[0] for choice in Profile.LOCATION_VISIBILITY_CHOICES}
        if value not in allowed:
            raise serializers.ValidationError("Invalid location visibility option.")
        return value

    def validate_location_visibility_friends(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("Must be a list of user ids.")
        cleaned: list[int] = []
        for item in value:
            try:
                cleaned.append(int(item))
            except (TypeError, ValueError) as exc:
                raise serializers.ValidationError("Friend ids must be integers.") from exc
        return list(dict.fromkeys(cleaned))

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        friend_ids = attrs.get("location_visibility_friends")
        if friend_ids is None or user is None or not getattr(user, "is_authenticated", False):
            return attrs

        from matching.models import Match
        from django.db.models import Q

        matched_ids = set()
        for u1, u2 in Match.objects.filter(Q(user1=user) | Q(user2=user)).values_list(
            "user1_id", "user2_id"
        ):
            if u1 != user.id:
                matched_ids.add(u1)
            if u2 != user.id:
                matched_ids.add(u2)

        invalid = [uid for uid in friend_ids if uid not in matched_ids]
        if invalid:
            raise serializers.ValidationError(
                {
                    "location_visibility_friends": (
                        "Only matched friends can be selected for location privacy."
                    )
                }
            )
        return attrs


class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "profile"]


class GoogleAuthSerializer(serializers.Serializer):
    id_token = serializers.CharField(required=False)
    code = serializers.CharField(required=False)
    redirect_uri = serializers.CharField(required=False)

    def validate(self, attrs):
        if attrs.get("id_token"):
            return attrs

        if attrs.get("code"):
            if not attrs.get("redirect_uri"):
                raise serializers.ValidationError(
                    {"redirect_uri": "This field is required when using an authorization code."}
                )
            return attrs

        raise serializers.ValidationError("Provide either id_token or code.")


class EmailOtpSendSerializer(serializers.Serializer):
    email = serializers.EmailField()


class EmailOtpVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(min_length=6, max_length=6)


class PasswordForgotSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(min_length=6, max_length=6)
    password = serializers.CharField(write_only=True, validators=[validate_password])


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    full_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    username = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ["username", "email", "password", "full_name"]

    def validate_email(self, value):
        from accounts.email_otp import is_email_verified_for_registration, normalize_email

        email = normalize_email(value)
        if not is_email_verified_for_registration(email):
            raise serializers.ValidationError(
                "Email address is not verified. Complete OTP verification first."
            )
        return email

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
