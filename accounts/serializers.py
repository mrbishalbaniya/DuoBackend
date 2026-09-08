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

MIN_PROFILE_PHOTOS = 1
MAX_PROFILE_PHOTOS = 3


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
            "live_latitude",
            "live_longitude",
            "live_location_updated_at",
            "is_verified",
            "is_onboarded",
            "app_language",
            "app_region",
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
            "live_latitude",
            "live_longitude",
            "live_location_updated_at",
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
            data.pop("live_latitude", None)
            data.pop("live_longitude", None)
            data.pop("live_location_updated_at", None)
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

        instance = getattr(self, "instance", None)
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None

        # Only enforce the photo minimum when this request actually touches
        # photo fields — don't block an unrelated edit (e.g. bio) just
        # because an existing account has fewer than 5 photos already saved.
        if "photo_url" in attrs or "photo_urls" in attrs:
            photo_url = attrs.get(
                "photo_url", getattr(instance, "photo_url", "") if instance else ""
            )
            photo_urls = attrs.get(
                "photo_urls", getattr(instance, "photo_urls", []) if instance else []
            )
            total = (1 if photo_url else 0) + len(photo_urls or [])
            if total < MIN_PROFILE_PHOTOS:
                raise serializers.ValidationError(
                    {
                        "photo_urls": (
                            f"Upload at least {MIN_PROFILE_PHOTOS} photo"
                            f"{'' if MIN_PROFILE_PHOTOS == 1 else 's'} to save your "
                            f"profile ({total} of {MIN_PROFILE_PHOTOS})."
                        )
                    }
                )
            if total > MAX_PROFILE_PHOTOS:
                raise serializers.ValidationError(
                    {
                        "photo_urls": (
                            f"You can upload at most {MAX_PROFILE_PHOTOS} photos "
                            f"({total} of {MAX_PROFILE_PHOTOS})."
                        )
                    }
                )

            # The core safety gate: a URL may only be added to the profile if
            # it's backed by an APPROVED ProfilePhoto row for this user. URLs
            # already on the profile before this request are grandfathered
            # through untouched (existing users aren't broken by unrelated
            # edits). Every discovery/matching/chat surface already reads
            # Profile.photo_url/photo_urls unconditionally — this is what
            # makes that safe without needing to change any of them.
            if user is not None and getattr(user, "is_authenticated", False):
                existing_urls = set()
                if instance is not None:
                    if getattr(instance, "photo_url", ""):
                        existing_urls.add(instance.photo_url)
                    existing_urls.update(getattr(instance, "photo_urls", None) or [])

                new_urls = set(photo_urls or [])
                if photo_url:
                    new_urls.add(photo_url)
                added_urls = new_urls - existing_urls

                if added_urls:
                    from photo_verification.constants import ModerationStatus
                    from photo_verification.models import ProfilePhoto

                    approved_urls = set(
                        ProfilePhoto.objects.filter(
                            user=user,
                            status=ModerationStatus.APPROVED,
                            url__in=added_urls,
                        ).values_list("url", flat=True)
                    )
                    if added_urls - approved_urls:
                        raise serializers.ValidationError(
                            {
                                "photo_urls": (
                                    "One or more photos haven't finished moderation yet. "
                                    "Please wait for approval, or remove them and try again."
                                )
                            }
                        )

        # Server-side 18+ enforcement — previously frontend-only
        # (registrationSchema.ts). Never trust the client for this.
        age = attrs.get("age")
        if age is not None and age != "" and int(age) < 18:
            raise serializers.ValidationError({"age": "You must be at least 18 years old."})

        if attrs.get("location_ghost_mode"):
            attrs["live_latitude"] = None
            attrs["live_longitude"] = None
            attrs["live_location_updated_at"] = None
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


class DeleteAccountSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    full_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    username = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ["username", "email", "password", "full_name"]

    def validate_email(self, value):
        from accounts.email_otp import normalize_email

        return normalize_email(value)

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
