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
from .models import Swipe, Match
from .serializers import SwipeSerializer, MatchSerializer, LikedProfileSerializer, mask_profile_for_paywall
from chat.models import Conversation
from subscriptions.services import user_has_active_subscription


class SwipeView(APIView):
    """Record a swipe and check for mutual match."""

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

        return Response({
            'action': action,
            'is_match': is_match,
            'match': match_data,
        })

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
    ids = set()
    for match in Match.objects.filter(Q(user1=user) | Q(user2=user)):
        ids.add(match.get_other_user(user).id)
    return ids


class MatchListView(APIView):
    """List all matches for the current user."""

    @extend_schema(
        tags=["Matching"],
        summary="List my matches",
        responses={200: MatchSerializer(many=True)},
    )
    def get(self, request):
        matches = Match.objects.filter(
            Q(user1=request.user) | Q(user2=request.user)
        ).order_by('-matched_at')
        serializer = MatchSerializer(matches, many=True, context={'request': request})
        return Response(serializer.data)


class LikedByYouView(APIView):
    """Profiles the current user liked that are not mutual matches yet."""

    @extend_schema(
        tags=["Matching"],
        summary="List profiles liked by me (pending)",
        responses={200: LikedProfileSerializer(many=True)},
    )
    def get(self, request):
        matched_ids = _matched_user_ids(request.user)
        swipes = (
            Swipe.objects.filter(
                from_user=request.user,
                action__in=['LIKE', 'SUPERLIKE'],
            )
            .exclude(to_user_id__in=matched_ids)
            .select_related('to_user__profile')
            .order_by('-created_at')
        )
        serializer = LikedProfileSerializer(swipes, many=True, context={'request': request})
        return Response(serializer.data)


class LikesYouView(APIView):
    """Profiles that liked the current user but have not been liked back yet."""

    @extend_schema(
        tags=["Matching"],
        summary="List profiles that liked me (pending)",
        responses={200: LikedProfileSerializer(many=True)},
    )
    def get(self, request):
        matched_ids = _matched_user_ids(request.user)
        liked_back_ids = Swipe.objects.filter(
            from_user=request.user,
            action__in=['LIKE', 'SUPERLIKE'],
        ).values_list('to_user_id', flat=True)

        swipes = (
            Swipe.objects.filter(
                to_user=request.user,
                action__in=['LIKE', 'SUPERLIKE'],
            )
            .exclude(from_user_id__in=matched_ids)
            .exclude(from_user_id__in=liked_back_ids)
            .select_related('from_user__profile')
            .order_by('-created_at')
        )

        is_premium = user_has_active_subscription(request.user)
        serializer = LikedProfileSerializer(
            swipes,
            many=True,
            context={'request': request, 'locked': not is_premium},
        )
        results = serializer.data

        if not is_premium:
            for item in results:
                original = item.get('profile') or {}
                item['locked'] = True
                item['profile'] = mask_profile_for_paywall(
                    original,
                    swipe_id=item.get('swipe_id'),
                )

        return Response(
            {
                'is_premium': is_premium,
                'premium_required': not is_premium and len(results) > 0,
                'count': len(results),
                'results': results,
            }
        )


class SkippedByYouView(APIView):
    """Profiles the current user passed on (skipped)."""

    @extend_schema(
        tags=["Matching"],
        summary="List profiles I passed on",
        responses={200: LikedProfileSerializer(many=True)},
    )
    def get(self, request):
        swipes = (
            Swipe.objects.filter(
                from_user=request.user,
                action='SKIP',
            )
            .select_related('to_user__profile')
            .order_by('-created_at')
        )
        serializer = LikedProfileSerializer(swipes, many=True, context={'request': request})
        return Response(serializer.data)


@extend_schema_view(
    get=extend_schema(tags=["Matching"], summary="Get match compatibility insights"),
)
class MatchInsightView(RetrieveAPIView):
    """Get detailed compatibility insights for a specific match."""
    serializer_class = MatchSerializer

    def get_queryset(self):
        return Match.objects.filter(
            Q(user1=self.request.user) | Q(user2=self.request.user)
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
