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
    RewindSerializer,
    SwipeSerializer,
    UnlikeSerializer,
    MatchSerializer,
    LikedProfileSerializer,
    VisitedProfileSerializer,
    mask_profile_for_paywall,
)
from accounts.throttling import SwipeRateThrottle
from chat.services import users_are_blocked
from subscriptions.services import (
    FEATURE_REWIND,
    FEATURE_UNLIMITED_LIKES,
    FEATURE_VISITED_YOU,
    FEATURE_WHO_LIKED_YOU,
    user_has_active_subscription,
)
from duo_project.query_optimization import apply_list_window, get_matched_user_ids
from duo_project.cache.invalidation import invalidate_user_caches
from duo_project.cache import api_cache, get_user_cache_version
from duo_project.cache import keys as cache_keys
from duo_project.cache import ttl as cache_ttl
from .serializer_context import matching_list_context, profiles_from_swipes, profiles_from_visits
from .likes import LIKE_ACTIONS, get_like_quota, record_like
from .services import get_existing_match


class SwipeView(APIView):
    """Record a swipe and check for a mutual match.

    Rules:
    - No self-swipes; the target must be an active, unblocked user.
    - Left swipes (SKIP) are unlimited.
    - Free users get ``FREE_LIKES_PER_WINDOW`` Likes per rolling
      ``FREE_LIKES_WINDOW_HOURS``; an Unlimited likes pass lifts the limit.
      Only successful new Likes count (see ``matching.likes``).
    - Repeating the same swipe is a no-op (``duplicate: true``), never a
      second Like against the quota. Changing SKIP to LIKE is allowed;
      changing a Like on someone you matched with is not.
    - A Like on someone who already liked you creates exactly one Match.

    Every response carries the viewer's like quota (``likes_remaining``,
    ``reset_at``, ``likes``). Hitting the limit returns 429 with
    ``code: "like_limit_reached"``.
    """

    throttle_classes = [SwipeRateThrottle]

    @extend_schema(
        tags=["Matching"],
        summary="Swipe on a profile (like, skip, or superlike)",
        request=SwipeSerializer,
        responses={
            200: OpenApiResponse(description="Swipe recorded; includes match and like quota."),
            400: OpenApiResponse(description="Invalid swipe, e.g. on yourself."),
            404: OpenApiResponse(description="User not found."),
            409: OpenApiResponse(description="Already matched; the Like can't be changed."),
            429: OpenApiResponse(description="Free Like limit reached for this window."),
        },
    )
    def post(self, request):
        serializer = SwipeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        to_user_id = serializer.validated_data["to_user_id"]
        action = serializer.validated_data["action"]
        is_like = action in LIKE_ACTIONS

        if to_user_id == request.user.id:
            return Response(
                {"detail": "You can't swipe on yourself.", "code": "self_swipe"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        to_user = User.objects.filter(id=to_user_id, is_active=True).first()
        if to_user is None:
            return Response({"detail": "User not found.", "code": "not_found"}, status=404)

        if users_are_blocked(request.user, to_user):
            return Response({"detail": "User not available.", "code": "blocked"}, status=403)

        outcome = self._run_with_retry(lambda: self._apply_swipe(request.user, to_user, action))
        quota = get_like_quota(request.user)

        if outcome["result"] == "limit":
            return Response(
                {
                    "detail": (
                        f"You've used all {quota.limit} free Likes. "
                        "You can still pass on profiles, or get Unlimited likes."
                    ),
                    "code": "like_limit_reached",
                    "feature": FEATURE_UNLIMITED_LIKES,
                    **self._quota_fields(quota),
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        if outcome["result"] == "matched_locked":
            return Response(
                {
                    "detail": "You're matched with this person, so this swipe can't be changed.",
                    "code": "already_matched",
                    **self._quota_fields(quota),
                },
                status=status.HTTP_409_CONFLICT,
            )

        match = outcome.get("match")
        is_match = bool(outcome.get("match_created"))
        match_data = MatchSerializer(match, context={"request": request}).data if is_match else None

        # Notify only after the transaction committed.
        if is_match:
            from notifications.dispatch import dispatch_match_push

            dispatch_match_push(match=match)
        elif is_like and outcome["result"] == "created":
            from notifications.dispatch import dispatch_like_push

            dispatch_like_push(from_user=request.user, to_user=to_user, action=action)

        return Response(
            {
                "action": action,
                "duplicate": outcome["result"] == "duplicate",
                "is_match": is_match,
                "match": match_data,
                **self._quota_fields(quota),
            }
        )

    @staticmethod
    def _quota_fields(quota) -> dict:
        data = quota.as_dict()
        return {
            "likes_remaining": data["likes_remaining"],
            "reset_at": data["reset_at"],
            "likes": data,
        }

    @staticmethod
    def _apply_swipe(from_user, to_user, action) -> dict:
        """All reads and writes for one swipe, serialised per user pair.

        Locking both user rows (in id order, so two opposite swipes can't
        deadlock) makes concurrent Likes by the same user see each other for
        the quota check, and makes A-likes-B racing B-likes-A create exactly
        one Match. SQLite ignores the row locks but serialises writers anyway.
        """
        is_like = action in LIKE_ACTIONS
        with transaction.atomic():
            list(
                User.objects.select_for_update()
                .filter(id__in=sorted({from_user.id, to_user.id}))
                .order_by("id")
                .values_list("id", flat=True)
            )

            existing = Swipe.objects.filter(from_user=from_user, to_user=to_user).first()
            existing_match = get_existing_match(from_user, to_user)

            if existing is not None and existing.action == action:
                return {"result": "duplicate", "match": existing_match}

            already_liked = existing is not None and existing.action in LIKE_ACTIONS
            if existing_match is not None and already_liked and not is_like:
                return {"result": "matched_locked"}

            counts_as_new_like = is_like and not already_liked
            if counts_as_new_like and get_like_quota(from_user).exhausted:
                return {"result": "limit"}

            if existing is None:
                Swipe.objects.create(from_user=from_user, to_user=to_user, action=action)
            else:
                existing.action = action
                existing.save(update_fields=["action"])

            if counts_as_new_like:
                record_like(from_user, to_user)

            match_created = False
            match = existing_match
            if is_like and match is None:
                liked_back = Swipe.objects.filter(
                    from_user=to_user, to_user=from_user, action__in=LIKE_ACTIONS
                ).exists()
                if liked_back:
                    from matching.services import create_match_between

                    match, match_created = create_match_between(
                        from_user,
                        to_user,
                        notify=False,
                        ensure_likes=False,
                        allow_blocked=True,
                    )

            return {
                "result": "created" if counts_as_new_like or existing is None else "updated",
                "match": match,
                "match_created": match_created,
            }

    @staticmethod
    def _run_with_retry(fn, *, attempts: int = 5):
        """Retry on SQLite 'database is locked' style errors."""
        for attempt in range(attempts):
            try:
                return fn()
            except OperationalError:
                if attempt == attempts - 1:
                    raise
                time.sleep(0.05 * (2**attempt))
        raise RuntimeError("unreachable")  # pragma: no cover


class LikeQuotaView(APIView):
    """The viewer's Like quota, for showing remaining Likes before swiping."""

    @extend_schema(tags=["Matching"], summary="Get my remaining Likes and reset time")
    def get(self, request):
        data = get_like_quota(request.user).as_dict()
        return Response({**data, "reset_at": data["reset_at"]})


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


class RewindView(APIView):
    """Premium: undo a left or right swipe so the profile returns to the deck.

    Body: {"to_user_id": <id>} to undo that swipe; omitted means the most
    recent one. Swipes that already produced a match can't be rewound.
    """

    @extend_schema(
        tags=["Matching"],
        summary="Rewind (undo) a swipe — premium",
        request=RewindSerializer,
        responses={
            200: OpenApiResponse(description="Swipe undone; returns the profile to show again."),
            402: OpenApiResponse(description="A Rewind pass is required."),
            404: OpenApiResponse(description="Nothing to rewind."),
            409: OpenApiResponse(description="Already matched with this person."),
        },
    )
    def post(self, request):
        if not user_has_active_subscription(request.user, FEATURE_REWIND):
            return Response(
                {
                    "detail": "Rewind is a premium feature. Get a Rewind pass to undo swipes.",
                    "premium_required": True,
                    "feature": FEATURE_REWIND,
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        serializer = RewindSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        to_user_id = serializer.validated_data.get("to_user_id")

        swipes = Swipe.objects.filter(from_user=request.user).select_related("to_user__profile")
        swipe = (
            swipes.filter(to_user_id=to_user_id).first()
            if to_user_id
            else swipes.order_by("-created_at", "-id").first()
        )
        if swipe is None:
            return Response({"detail": "There's no swipe to rewind."}, status=status.HTTP_404_NOT_FOUND)

        other = swipe.to_user
        if Match.objects.filter(
            Q(user1=request.user, user2=other) | Q(user1=other, user2=request.user)
        ).exists():
            return Response(
                {"detail": "You already matched with this person, so this swipe can't be undone."},
                status=status.HTTP_409_CONFLICT,
            )

        action = swipe.action
        swipe.delete()  # post_delete signal refreshes both users' cached lists

        profile_data = None
        profile = getattr(other, "profile", None)
        if profile is not None and not users_are_blocked(request.user, other):
            from accounts.serializer_context import profile_list_serializer_context
            from accounts.serializers import ProfileSerializer
            from matching.recommendation.scoring import candidate_distance_km, viewer_anchor

            _, viewer_coords = viewer_anchor(request.user.profile)
            profile.discover_distance_km = candidate_distance_km(viewer_coords, profile)
            context = profile_list_serializer_context(request, [profile])
            profile_data = ProfileSerializer(profile, context=context).data

        return Response({"undone_action": action, "profile": profile_data})


def _matched_user_ids(user):
    return get_matched_user_ids(user)


def _match_conversations(user) -> dict[int, str]:
    """other_user_id -> public conversation id, for every match of ``user``."""
    from chat.models import Conversation

    out: dict[int, str] = {}
    rows = Conversation.objects.filter(Q(match__user1=user) | Q(match__user2=user)).values_list(
        "public_id", "match__user1_id", "match__user2_id"
    )
    for public_id, u1, u2 in rows:
        out[u2 if u1 == user.id else u1] = public_id
    return out


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
                .select_related("user1__profile", "user2__profile", "conversation")
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
            # Only pending likes; matches are listed on the Matched tab.
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
            context = matching_list_context(request, profiles)
            context["match_conversations"] = _match_conversations(request.user)
            return LikedProfileSerializer(swipes, many=True, context=context).data

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

            # Pending likes plus people you already matched with (liked back
            # without a match yet is excluded: nothing left to do there).
            swipes = apply_list_window(
                Swipe.objects.filter(
                    to_user=request.user,
                    action__in=['LIKE', 'SUPERLIKE'],
                )
                .exclude(Q(from_user_id__in=liked_back_ids) & ~Q(from_user_id__in=matched_ids))
                .select_related('from_user__profile')
                .order_by('-created_at'),
                request,
                default_limit=200,
                max_limit=500,
            )

            is_premium = user_has_active_subscription(request.user, FEATURE_WHO_LIKED_YOU)
            profiles = profiles_from_swipes(swipes, request.user)
            context = matching_list_context(request, profiles, locked=not is_premium)
            context["match_conversations"] = _match_conversations(request.user)
            results = LikedProfileSerializer(swipes, many=True, context=context).data

            pending = [item for item in results if item.get('status') != 'matched']
            if not is_premium:
                # Like "Visited you": without the pass every card is locked,
                # matches included (no name, status or chat link leaks).
                for item in results:
                    original = item.get('profile') or {}
                    item['locked'] = True
                    item['status'] = None
                    item['conversation_id'] = None
                    item['profile'] = mask_profile_for_paywall(
                        original,
                        swipe_id=item.get('swipe_id'),
                    )

            return {
                'is_premium': is_premium,
                'premium_required': not is_premium and len(results) > 0,
                'count': len(results),
                'pending_count': len(pending) if is_premium else None,
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

            is_premium = user_has_active_subscription(request.user, FEATURE_VISITED_YOU)
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
        from matching.ai_insights import get_match_insights

        match = self.get_object()
        force = request.query_params.get("refresh") in {"1", "true"}
        # Scores are recomputed from the profiles and the AI text is stored on
        # the match (regenerated only when inputs change), so no response cache.
        insights = get_match_insights(match, force=force)
        insights["ai_provider"] = "claude" if insights.get("ai_generated") else None
        if not insights.get("ai_generated"):
            # Duo's own trained model (matching/ml); None until one is trained.
            from matching.ml.insights import local_insights

            local = local_insights(match, request.user)
            if local:
                insights.update(local)
                insights["ai_generated"] = True
                insights["ai_provider"] = "duo"
        data = MatchSerializer(match, context=self.get_serializer_context()).data
        data.update(insights)
        return Response(data)
