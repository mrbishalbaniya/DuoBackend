from django import forms
from django.contrib import admin, messages
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
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import path, reverse

from chat.services import users_are_blocked
from matching.services import create_match_between, get_existing_match

from .models import Match, Swipe


def _user_label(user: User) -> str:
    profile = getattr(user, "profile", None)
    name = (getattr(profile, "full_name", None) or "").strip()
    email = (user.email or "").strip()
    bits = [user.username]
    if name:
        bits.append(name)
    if email and email.lower() != user.username.lower():
        bits.append(email)
    bits.append(f"#{user.id}")
    return " - ".join(bits)


def _resolve_user_query(raw: str) -> User | None:
    value = (raw or "").strip()
    if not value:
        return None
    if value.isdigit():
        return User.objects.select_related("profile").filter(pk=int(value)).first()
    return (
        User.objects.select_related("profile")
        .filter(Q(username__iexact=value) | Q(email__iexact=value))
        .first()
    )


def _user_choice_queryset():
    return User.objects.select_related("profile").order_by("username")


class AdminCreateMatchForm(forms.Form):
    user1 = forms.ModelChoiceField(
        label="User A",
        queryset=_user_choice_queryset(),
        empty_label="Search and select a user…",
        widget=forms.Select(
            attrs={
                "class": "duo-user-select",
                "data-placeholder": "Search users…",
            }
        ),
        help_text="Search by username, name, email, or ID.",
    )
    user2 = forms.ModelChoiceField(
        label="User B",
        queryset=_user_choice_queryset(),
        empty_label="Search and select a user…",
        widget=forms.Select(
            attrs={
                "class": "duo-user-select",
                "data-placeholder": "Search users…",
            }
        ),
        help_text="Search by username, name, email, or ID.",
    )
    compatibility_score = forms.IntegerField(
        label="Compatibility score",
        required=False,
        min_value=0,
        max_value=100,
        initial=85,
        help_text="Optional. Leave blank to auto-generate a score.",
        widget=forms.NumberInput(attrs={"class": "vIntegerField", "min": 0, "max": 100}),
    )
    ensure_likes = forms.BooleanField(
        label="Create mutual LIKE swipes",
        required=False,
        initial=True,
        help_text="Recommended so the match looks normal in both users’ swipe history.",
    )
    notify_users = forms.BooleanField(
        label="Send match notifications",
        required=False,
        initial=True,
    )
    allow_blocked = forms.BooleanField(
        label="Allow even if users blocked each other",
        required=False,
        initial=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for key in ("user1", "user2"):
            value = self.initial.get(key)
            if isinstance(value, User):
                continue
            if value not in (None, ""):
                user = _resolve_user_query(str(value))
                if user:
                    self.initial[key] = user

        qs = _user_choice_queryset()
        self.fields["user1"].queryset = qs
        self.fields["user2"].queryset = qs
        self.fields["user1"].label_from_instance = _user_label
        self.fields["user2"].label_from_instance = _user_label

    def clean(self):
        cleaned = super().clean()
        user1 = cleaned.get("user1")
        user2 = cleaned.get("user2")
        if user1 and user2 and user1.id == user2.id:
            raise forms.ValidationError("Choose two different users.")
        cleaned["resolved_user1"] = user1
        cleaned["resolved_user2"] = user2
        return cleaned


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
        return request.user.is_staff

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "create-match/",
                self.admin_site.admin_view(self.create_match_view),
                name="matching_match_create_custom",
            ),
            path(
                "user-search/",
                self.admin_site.admin_view(self.user_search_view),
                name="matching_match_user_search",
            ),
            path(
                "user/<int:user_id>/",
                self.admin_site.admin_view(self.user_matches_view),
                name="matching_match_user",
            ),
        ]
        return custom_urls + urls

    def add_view(self, request, form_url="", extra_context=None):
        return HttpResponseRedirect(reverse("admin:matching_match_create_custom"))

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
            "create_match_url": reverse("admin:matching_match_create_custom"),
            "media": self.media,
        }
        return render(request, self.change_list_template, context)

    def user_search_view(self, request):
        q = (request.GET.get("q") or "").strip()
        users = _user_choice_queryset()
        if q:
            filters = (
                Q(username__icontains=q)
                | Q(email__icontains=q)
                | Q(profile__full_name__icontains=q)
            )
            if q.isdigit():
                filters |= Q(pk=int(q))
            users = users.filter(filters)
        users = users[:40]
        return JsonResponse(
            {
                "results": [
                    {"id": user.pk, "text": _user_label(user)}
                    for user in users
                ]
            }
        )

    def create_match_view(self, request):
        initial = {}
        if request.method == "GET":
            if request.GET.get("user1"):
                initial["user1"] = request.GET.get("user1")
            if request.GET.get("user2"):
                initial["user2"] = request.GET.get("user2")

        form = AdminCreateMatchForm(request.POST or None, initial=initial)
        preview = None

        if request.method == "POST" and form.is_valid():
            user1 = form.cleaned_data["resolved_user1"]
            user2 = form.cleaned_data["resolved_user2"]
            allow_blocked = form.cleaned_data["allow_blocked"]

            if users_are_blocked(user1, user2) and not allow_blocked:
                form.add_error(
                    None,
                    "These users have a block between them. Check “Allow even if users blocked each other” to force the match.",
                )
            else:
                existing = get_existing_match(user1, user2)
                if existing and "confirm_existing" not in request.POST:
                    preview = {
                        "user1": _user_label(user1),
                        "user2": _user_label(user2),
                        "existing": existing,
                    }
                else:
                    try:
                        match, created = create_match_between(
                            user1,
                            user2,
                            compatibility_score=form.cleaned_data.get("compatibility_score"),
                            ensure_likes=form.cleaned_data["ensure_likes"],
                            notify=form.cleaned_data["notify_users"],
                            allow_blocked=allow_blocked,
                        )
                    except ValueError as exc:
                        form.add_error(None, str(exc))
                    else:
                        if created:
                            messages.success(
                                request,
                                f"Created match #{match.id}: {_user_label(user1)} ❤ {_user_label(user2)} "
                                f"({match.compatibility_score}% compatibility).",
                            )
                        else:
                            messages.info(
                                request,
                                f"Match already existed (#{match.id}). Conversation ensured.",
                            )
                        return HttpResponseRedirect(
                            reverse("admin:matching_match_user", args=[user1.id])
                        )

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Create custom match",
            "form": form,
            "preview": preview,
            "back_url": reverse("admin:matching_match_changelist"),
            "user_search_url": reverse("admin:matching_match_user_search"),
            "media": self.media,
        }
        return render(request, "admin/matching/match/create_match.html", context)

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
            "create_match_url": reverse("admin:matching_match_create_custom"),
            "media": self.media,
        }
        return render(request, "admin/matching/match/user_matches.html", context)
