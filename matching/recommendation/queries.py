from __future__ import annotations

from django.db.models import Count, Q, QuerySet

from accounts.models import Profile
from duo_project.query_optimization import get_matched_user_ids
from duo_project.security.privacy import blocked_user_ids
from matching.models import Swipe


def build_eligible_queryset(user) -> QuerySet[Profile]:
  """Eligible discover pool with popularity annotations and no N+1 user loads."""
  swiped_ids = Swipe.objects.filter(from_user=user).values_list("to_user_id", flat=True)
  matched_ids = get_matched_user_ids(user)
  blocked = blocked_user_ids(user.id)

  return (
    Profile.objects.select_related("user")
    .exclude(user=user)
    .exclude(user_id__in=swiped_ids)
    .exclude(user_id__in=matched_ids)
    .exclude(user_id__in=blocked)
    .filter(is_onboarded=True)
    .annotate(
      likes_received_count=Count(
        "user__swipes_received",
        filter=Q(user__swipes_received__action__in=["LIKE", "SUPERLIKE"]),
        distinct=True,
      ),
      matches_as_user1_count=Count("user__matches_as_user1", distinct=True),
      matches_as_user2_count=Count("user__matches_as_user2", distinct=True),
    )
  )
