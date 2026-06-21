import random
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import RetrieveAPIView
from django.contrib.auth.models import User
from django.db.models import Q
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from .models import Swipe, Match
from .serializers import SwipeSerializer, MatchSerializer
from chat.models import Conversation


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

        swipe, created = Swipe.objects.update_or_create(
            from_user=request.user,
            to_user=to_user,
            defaults={'action': action}
        )

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
