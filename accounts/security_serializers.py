from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

import logging

logger = logging.getLogger("duo.auth")


class DuoTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        request = self.context.get("request")
        credentials = {
            self.username_field: attrs.get(self.username_field),
            "password": attrs.get("password"),
        }
        user = authenticate(request=request, **credentials)
        if user is None:
            raise AuthenticationFailed("No active account found with the given credentials")

        from security.services import security_service

        try:
            requires_2fa = security_service.login_requires_2fa(user)
        except Exception:
            logger.exception("login_requires_2fa_failed user_id=%s", user.id)
            requires_2fa = False

        if requires_2fa:
            challenge = security_service.create_login_challenge(user)
            tfa = security_service.get_or_create_2fa(user)
            raise serializers.ValidationError({
                "requires_2fa": [True],
                "challenge_token": [challenge],
                "methods": [tfa.method] if tfa.method else [],
            })

        self.user = user
        self.session_recorded = False
        refresh = self.get_token(user)
        data = {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }
        if request is not None:
            try:
                security_service.record_login(
                    user,
                    request,
                    success=True,
                    refresh_token=data["refresh"],
                )
                self.session_recorded = True
            except Exception:
                logger.exception("record_login_failed user_id=%s", user.id)
        return data

    def _resolve_user(self, attrs):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        username = attrs.get(self.username_field, "")
        return User.objects.filter(username=username).first()
