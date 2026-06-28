from django.contrib import admin
from django.contrib.auth.models import User
from django.db.models import (
    Count,
    ExpressionWrapper,
    F,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Value,
)
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, render
from django.urls import path, reverse

from .models import Match, Swipe


@admin.register(Swipe)
class SwipeAdmin(admin.ModelAdmin):
    list_display = ["from_user", "to_user", "action", "created_at"]
    change_list_template = "admin/matching/swipe/user_list.html"

    def has_add_permission(self, request):
        return False

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "user/<int:user_id>/",
                self.admin_site.admin_view(self.user_swipes_view),
                name="matching_swipe_user",
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        search_query = request.GET.get("q", "").strip()

        users = (
            User.objects.filter(swipes_made__isnull=False)
            .select_related("profile")
            .annotate(
                swipe_count=Count("swipes_made", distinct=True),
                like_count=Count(
                    "swipes_made",
                    filter=Q(swipes_made__action="LIKE"),
                    distinct=True,
                ),
                skip_count=Count(
                    "swipes_made",
                    filter=Q(swipes_made__action="SKIP"),
                    distinct=True,
                ),
                superlike_count=Count(
                    "swipes_made",
                    filter=Q(swipes_made__action="SUPERLIKE"),
                    distinct=True,
                ),
            )
            .distinct()
            .order_by("-swipe_count", "username")
        )

        if search_query:
            users = users.filter(
                Q(username__icontains=search_query)
                | Q(email__icontains=search_query)
                | Q(profile__full_name__icontains=search_query)
                | Q(profile__phone_number__icontains=search_query)
            )

        context = {
            **self.admin_site.each_context(request),
            **(extra_context or {}),
            "opts": self.model._meta,
            "title": "Select user to view swipes",
            "users": users,
            "search_query": search_query,
            "media": self.media,
        }
        return render(request, self.change_list_template, context)

    def user_swipes_view(self, request, user_id):
        user = get_object_or_404(User.objects.select_related("profile"), pk=user_id)
        swipes = (
            Swipe.objects.filter(from_user=user)
            .select_related("to_user", "to_user__profile")
            .order_by("-created_at")
        )

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": f"Swipes by {user.username}",
            "user_obj": user,
            "swipes": swipes,
            "back_url": reverse("admin:matching_swipe_changelist"),
            "media": self.media,
        }
        return render(request, "admin/matching/swipe/user_swipes.html", context)


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ["user1", "user2", "compatibility_score", "matched_at"]
    change_list_template = "admin/matching/match/user_list.html"

    def has_add_permission(self, request):
        return False

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "user/<int:user_id>/",
                self.admin_site.admin_view(self.user_matches_view),
                name="matching_match_user",
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        search_query = request.GET.get("q", "").strip()

        match_as_user1 = (
            Match.objects.filter(user1=OuterRef("pk"))
            .values("user1")
            .annotate(cnt=Count("id"))
            .values("cnt")
        )
        match_as_user2 = (
            Match.objects.filter(user2=OuterRef("pk"))
            .values("user2")
            .annotate(cnt=Count("id"))
            .values("cnt")
        )

        users = (
            User.objects.filter(
                Q(matches_as_user1__isnull=False) | Q(matches_as_user2__isnull=False)
            )
            .select_related("profile")
            .annotate(
                match_count_as_user1=Coalesce(
                    Subquery(match_as_user1), Value(0), output_field=IntegerField()
                ),
                match_count_as_user2=Coalesce(
                    Subquery(match_as_user2), Value(0), output_field=IntegerField()
                ),
            )
            .annotate(
                match_count=ExpressionWrapper(
                    F("match_count_as_user1") + F("match_count_as_user2"),
                    output_field=IntegerField(),
                )
            )
            .distinct()
            .order_by("-match_count", "username")
        )

        if search_query:
            users = users.filter(
                Q(username__icontains=search_query)
                | Q(email__icontains=search_query)
                | Q(profile__full_name__icontains=search_query)
                | Q(profile__phone_number__icontains=search_query)
            )

        context = {
            **self.admin_site.each_context(request),
            **(extra_context or {}),
            "opts": self.model._meta,
            "title": "Select user to view matches",
            "users": users,
            "search_query": search_query,
            "media": self.media,
        }
        return render(request, self.change_list_template, context)

    def user_matches_view(self, request, user_id):
        user = get_object_or_404(User.objects.select_related("profile"), pk=user_id)
        matches = (
            Match.objects.filter(Q(user1=user) | Q(user2=user))
            .select_related(
                "user1",
                "user2",
                "user1__profile",
                "user2__profile",
            )
            .order_by("-matched_at")
        )

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": f"Matches for {user.username}",
            "user_obj": user,
            "matches": matches,
            "back_url": reverse("admin:matching_match_changelist"),
            "media": self.media,
        }
        return render(request, "admin/matching/match/user_matches.html", context)
