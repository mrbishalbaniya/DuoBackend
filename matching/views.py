import random
import time

from django.db import OperationalError, transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import RetrieveAPIView
from django.contrib.auth.models import User
from django.db.models import Q
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from .models import Swipe, Match, ProfileVisit
from .serializers import (
    SwipeSerializer,
    UnlikeSerializer,
    MatchSerializer,
    LikedProfileSerializer,
    VisitedProfileSerializer,
    mask_profile_for_paywall,
)
from accounts.throttling import SwipeRateThrottle
from chat.models import Conversation
from chat.services import users_are_blocked
from subscriptions.services import user_has_active_subscription
from duo_project.query_optimization import apply_list_window, get_matched_user_ids
from duo_project.cache.invalidation import invalidate_user_caches
from duo_project.cache import api_cache, get_user_cache_version
from duo_project.cache import keys as cache_keys
from duo_project.cache import ttl as cache_ttl
from .serializer_context import matching_list_context, profiles_from_swipes, profiles_from_visits


class SwipeView(APIView):
    """Record a swipe and check for mutual match."""

    throttle_classes = [SwipeRateThrottle]

    @extend_schema(
        tags=["Matching"],
        summary="Swipe on a profile (like, skip, or superlike)",
        request=SwipeSerializer,
    )
    def post(self, request):
        serializer = SwipeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        to_user_id = serializer.validated_data['to_user_id']
        action = serializer.validated_data['action']

        try:
            to_user = User.objects.get(id=to_user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)

        if users_are_blocked(request.user, to_user):
            return Response({"error": "User not available"}, status=403)

        self._upsert_swipe(request.user, to_user, action)

        is_match = False
        match_data = None

        if action in ('LIKE', 'SUPERLIKE'):
            reverse_swipe = Swipe.objects.filter(
                from_user=to_user,
                to_user=request.user,
                action__in=['LIKE', 'SUPERLIKE']
            ).exists()

            if reverse_swipe:
                existing_match = Match.objects.filter(
                    Q(user1=request.user, user2=to_user) |
                    Q(user1=to_user, user2=request.user)
                ).first()

                if not existing_match:
                    match = self._create_match(request.user, to_user)
                    is_match = True
                    match_data = MatchSerializer(match, context={'request': request}).data
                    from notifications.dispatch import dispatch_match_push

                    dispatch_match_push(match=match)
            else:
                from notifications.dispatch import dispatch_like_push

                dispatch_like_push(
                    from_user=request.user,
                    to_user=to_user,
                    action=action,
                )

        return Response({
            'action': action,
            'is_match': is_match,
            'match': match_data,
        })


class UnlikeView(APIView):
    """Remove a pending like or superlike before a match is formed."""

    @extend_schema(
        tags=["Matching"],
        summary="Unlike a profile (withdraw sent like)",
        request=UnlikeSerializer,
    )
    def post(self, request):
        serializer = UnlikeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        to_user_id = serializer.validated_data["to_user_id"]
        swipe = (
            Swipe.objects.filter(
                from_user=request.user,
                to_user_id=to_user_id,
                action__in=["LIKE", "SUPERLIKE"],
            )
            .select_related("to_user")
            .first()
        )
        if swipe is None:
            return Response({"detail": "Like not found."}, status=status.HTTP_404_NOT_FOUND)

        matched = Match.objects.filter(
            Q(user1=request.user, user2_id=to_user_id)
            | Q(user1_id=to_user_id, user2=request.user)
        ).exists()
        if matched:
            return Response(
                {"detail": "Cannot unlike someone you are matched with."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        other_user_id = swipe.to_user_id
        swipe.delete()
        invalidate_user_caches(request.user.id, reason="unlike")
        invalidate_user_caches(other_user_id, reason="unlike")
        return Response({"detail": "Like removed."})

    @staticmethod
    def _upsert_swipe(from_user, to_user, action, *, attempts: int = 5):
        last_error = None
        for attempt in range(attempts):
            try:
                with transaction.atomic():
                    return Swipe.objects.update_or_create(
                        from_user=from_user,
                        to_user=to_user,
                        defaults={"action": action},
                    )
            except OperationalError as exc:
                last_error = exc
                if attempt == attempts - 1:
                    raise
                time.sleep(0.05 * (2**attempt))
        raise last_error  # pragma: no cover

    def _create_match(self, user1, user2):
        p1 = user1.profile
        p2 = user2.profile

        values = random.randint(75, 98)
        lifestyle = random.randint(60, 95)
        career = random.randint(65, 95)
        hobbies = random.randint(50, 90)
        overall = int((values * 0.35) + (lifestyle * 0.25) + (career * 0.25) + (hobbies * 0.15))

        all_interests = ['Hiking', 'Reading', 'Cooking', 'Travel', 'Music', 'Yoga',
                         'Photography', 'Dancing', 'Classic Rock', 'Philanthropy']
        shared = random.sample(all_interests, random.randint(3, 6))

        sparks = [
            f"Both passionate about adventure travel and mountains",
            f"Strong mutual focus on family-oriented celebrations",
            f"Shared appreciation for traditional cultural values",
        ]

        match = Match.objects.create(
            user1=user1,
            user2=user2,
            compatibility_score=overall,
            values_score=values,
            lifestyle_score=lifestyle,
            career_score=career,
            hobbies_score=hobbies,
            spark_factors=random.sample(sparks, 2),
            shared_interests=shared,
            vision_insight=f"Both express a desire for an urban lifestyle while maintaining strong ties to traditional ancestral homes during festivals. This alignment ensures no geographical friction in the coming years.",
            communication_insight=f"{p1.full_name or 'User 1'} values directness and logic, while {p2.full_name or 'User 2'} prioritizes emotional resonance. This balanced pairing often results in highly effective problem-solving in partnerships.",
        )
        # Auto-create conversation for the match
        Conversation.objects.create(match=match)
        return match


def _matched_user_ids(user):
    return get_matched_user_ids(user)


class MatchListView(APIView):
    """List all matches for the current user."""

    @extend_schema(
        tags=["Matching"],
        summary="List my matches",
        responses={200: MatchSerializer(many=True)},
    )
    def get(self, request):
        version = get_user_cache_version(request.user.id)
        limit, offset = cache_keys.list_window_suffix(request)
        cache_key = cache_keys.matches(request.user.id, version, limit, offset)

        def build():
            matches = apply_list_window(
                Match.objects.filter(Q(user1=request.user) | Q(user2=request.user))
                .select_related("user1__profile", "user2__profile")
                .order_by("-matched_at"),
                request,
                default_limit=200,
                max_limit=500,
            )
            profiles = []
            for match in matches:
                profiles.append(match.get_other_user(request.user).profile)
            return MatchSerializer(
                matches,
                many=True,
                context=matching_list_context(request, profiles),
            ).data

        return Response(
            api_cache.get_or_set(cache_key, build, cache_ttl.MATCHES, label="matches")
        )


class LikedByYouView(APIView):
    """Profiles the current user liked that are not mutual matches yet."""

    @extend_schema(
        tags=["Matching"],
        summary="List profiles liked by me (pending)",
        responses={200: LikedProfileSerializer(many=True)},
    )
    def get(self, request):
        version = get_user_cache_version(request.user.id)
        limit, offset = cache_keys.list_window_suffix(request)
        cache_key = cache_keys.liked_by_you(request.user.id, version, limit, offset)

        def build():
            matched_ids = _matched_user_ids(request.user)
            swipes = apply_list_window(
                Swipe.objects.filter(
                    from_user=request.user,
                    action__in=['LIKE', 'SUPERLIKE'],
                )
                .exclude(to_user_id__in=matched_ids)
                .select_related('to_user__profile')
                .order_by('-created_at'),
                request,
                default_limit=200,
                max_limit=500,
            )
            profiles = profiles_from_swipes(swipes, request.user)
            return LikedProfileSerializer(
                swipes,
                many=True,
                context=matching_list_context(request, profiles),
            ).data

        return Response(
            api_cache.get_or_set(cache_key, build, cache_ttl.LIKES_OUT, label="liked_by_you")
        )


class LikesYouView(APIView):
    """Profiles that liked the current user but have not been liked back yet."""

    @extend_schema(
        tags=["Matching"],
        summary="List profiles that liked me (pending)",
        responses={200: LikedProfileSerializer(many=True)},
    )
    def get(self, request):
        version = get_user_cache_version(request.user.id)
        limit, offset = cache_keys.list_window_suffix(request)
        cache_key = cache_keys.likes_you(request.user.id, version, limit, offset)

        def build():
            matched_ids = _matched_user_ids(request.user)
            liked_back_ids = Swipe.objects.filter(
                from_user=request.user,
                action__in=['LIKE', 'SUPERLIKE'],
            ).values_list('to_user_id', flat=True)

            swipes = apply_list_window(
                Swipe.objects.filter(
                    to_user=request.user,
                    action__in=['LIKE', 'SUPERLIKE'],
                )
                .exclude(from_user_id__in=matched_ids)
                .exclude(from_user_id__in=liked_back_ids)
                .select_related('from_user__profile')
                .order_by('-created_at'),
                request,
                default_limit=200,
                max_limit=500,
            )

            is_premium = user_has_active_subscription(request.user)
            profiles = profiles_from_swipes(swipes, request.user)
            results = LikedProfileSerializer(
                swipes,
                many=True,
                context=matching_list_context(request, profiles, locked=not is_premium),
            ).data

            if not is_premium:
                for item in results:
                    original = item.get('profile') or {}
                    item['locked'] = True
                    item['profile'] = mask_profile_for_paywall(
                        original,
                        swipe_id=item.get('swipe_id'),
                    )

            return {
                'is_premium': is_premium,
                'premium_required': not is_premium and len(results) > 0,
                'count': len(results),
                'results': results,
            }

        return Response(
            api_cache.get_or_set(cache_key, build, cache_ttl.LIKES_IN, label="likes_you")
        )


class ProfileVisitorsView(APIView):
    """Users who viewed the current user's profile (premium reveals full details)."""

    @extend_schema(
        tags=["Matching"],
        summary="List users who viewed my profile",
        responses={200: VisitedProfileSerializer(many=True)},
    )
    def get(self, request):
        version = get_user_cache_version(request.user.id)
        limit, offset = cache_keys.list_window_suffix(request)
        cache_key = cache_keys.profile_visitors(request.user.id, version, limit, offset)

        def build():
            visits = apply_list_window(
                ProfileVisit.objects.filter(viewed_user=request.user)
                .exclude(viewer=request.user)
                .select_related("viewer__profile")
                .order_by("-last_visited_at"),
                request,
                default_limit=200,
                max_limit=500,
            )

            is_premium = user_has_active_subscription(request.user)
            profiles = profiles_from_visits(visits)
            results = VisitedProfileSerializer(
                visits,
                many=True,
                context=matching_list_context(request, profiles, locked=not is_premium),
            ).data

            if not is_premium:
                for item, visit in zip(results, visits):
                    original = item.get("profile") or {}
                    item["locked"] = True
                    item["profile"] = mask_profile_for_paywall(
                        original,
                        visit_id=visit.id,
                    )

            return {
                "is_premium": is_premium,
                "premium_required": not is_premium and len(results) > 0,
                "count": len(results),
                "results": results,
            }

        return Response(
            api_cache.get_or_set(cache_key, build, cache_ttl.VISITORS, label="profile_visitors")
        )


class SkippedByYouView(APIView):
    """Profiles the current user passed on (skipped)."""

    @extend_schema(
        tags=["Matching"],
        summary="List profiles I passed on",
        responses={200: LikedProfileSerializer(many=True)},
    )
    def get(self, request):
        version = get_user_cache_version(request.user.id)
        limit, offset = cache_keys.list_window_suffix(request)
        cache_key = cache_keys.skipped_by_you(request.user.id, version, limit, offset)

        def build():
            swipes = apply_list_window(
                Swipe.objects.filter(
                    from_user=request.user,
                    action='SKIP',
                )
                .select_related('to_user__profile')
                .order_by('-created_at'),
                request,
                default_limit=200,
                max_limit=500,
            )
            profiles = profiles_from_swipes(swipes, request.user)
            return LikedProfileSerializer(
                swipes,
                many=True,
                context=matching_list_context(request, profiles),
            ).data

        return Response(
            api_cache.get_or_set(cache_key, build, cache_ttl.LIKES_OUT, label="skipped_by_you")
        )


@extend_schema_view(
    get=extend_schema(tags=["Matching"], summary="Get match compatibility insights"),
)
class MatchInsightView(RetrieveAPIView):
    """Get detailed compatibility insights for a specific match."""
    serializer_class = MatchSerializer

    def get_queryset(self):
        return Match.objects.filter(
            Q(user1=self.request.user) | Q(user2=self.request.user)
        ).select_related("user1__profile", "user2__profile")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        match = self.get_object()
        other_profile = match.get_other_user(self.request.user).profile
        context.update(matching_list_context(self.request, [other_profile]))
        return context

    def retrieve(self, request, *args, **kwargs):
        match = self.get_object()
        cache_key = cache_keys.match_insight(match.id, request.user.id)

        def build():
            other_profile = match.get_other_user(request.user).profile
            context = super().get_serializer_context()
            context.update(matching_list_context(request, [other_profile]))
            return MatchSerializer(match, context=context).data

        data = api_cache.get_or_set(
            cache_key,
            build,
            cache_ttl.MATCH_INSIGHT,
            label="match_insight",
        )
        return Response(data)
