from django.contrib.auth import authenticate
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

import logging

logger = logging.getLogger("duo.auth")


class DuoTokenObtainPairSerializer(TokenObtainPairSerializer):
    @staticmethod
    def _candidate_usernames(identifier):
        """Usernames to try for a login identifier that may be a username or an email.

        Registration treats email as the unique account key, so login must accept
        the email too, even when the account has a custom username.
        """
        from django.contrib.auth import get_user_model

        User = get_user_model()
        if not identifier:
            return []
        active = User.objects.filter(is_active=True)
        # When one email has several accounts (old duplicate sign-ups), try the
        # finished, most recently used account first so login doesn't land on
        # an abandoned half-registered copy.
        ordering = ("-profile__is_onboarded", "-last_login", "-id")
        by_username = active.filter(username__iexact=identifier).order_by(*ordering)
        by_email = active.filter(email__iexact=identifier).order_by(*ordering)
        if "@" in identifier:
            groups = [by_email, by_username]
        else:
            groups = [by_username, by_email]
        candidates = []
        for group in groups:
            for username in group.values_list("username", flat=True):
                if username not in candidates:
                    candidates.append(username)
        if identifier not in candidates:
            candidates.append(identifier)
        return candidates
        matches = User.objects.filter(is_active=True)
        by_username = matches.filter(username__iexact=identifier).values_list("username", flat=True)
        by_email = matches.filter(email__iexact=identifier).values_list("username", flat=True)
        for username in list(by_username) + list(by_email):
            if username not in candidates:
                candidates.append(username)
        return candidates

    def validate(self, attrs):
        request = self.context.get("request")
        identifier = (attrs.get(self.username_field) or "").strip()
        password = attrs.get("password")
        user = None
        for username in self._candidate_usernames(identifier):
            user = authenticate(
                request=request,
                **{self.username_field: username, "password": password},
            )
            if user is not None:
                break
        if user is None:
            try:
                from security.services import security_service

                security_service.record_failed_password_login(
                    request,
                    username=attrs.get(self.username_field, ""),
                )
            except Exception:
                logger.exception("failed_login_record_error")
            raise AuthenticationFailed("No active account found with the given credentials")

        from security.services import security_service

        try:
            requires_2fa = security_service.login_requires_2fa(user, request)
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
        
        # Include user data in the login response to avoid extra /me request
        from .serializers import UserSerializer
        data["user"] = UserSerializer(user).data
        
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
