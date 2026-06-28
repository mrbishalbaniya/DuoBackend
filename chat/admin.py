from django.contrib import admin
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render
from django.urls import path, reverse

from .models import Conversation, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["id", "match", "created_at"]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["sender", "content", "timestamp", "is_read"]
    change_list_template = "admin/chat/message/user_list.html"

    def has_add_permission(self, request):
        return False

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "user/<int:user_id>/",
                self.admin_site.admin_view(self.user_messages_view),
                name="chat_message_user",
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        search_query = request.GET.get("q", "").strip()

        users = (
            User.objects.filter(message__isnull=False)
            .select_related("profile")
            .annotate(
                message_count=Count("message", distinct=True),
                unread_sent_count=Count(
                    "message",
                    filter=Q(message__is_read=False),
                    distinct=True,
                ),
                deleted_count=Count(
                    "message",
                    filter=Q(message__is_deleted_for_everyone=True),
                    distinct=True,
                ),
            )
            .distinct()
            .order_by("-message_count", "username")
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
            "title": "Select user to view messages",
            "users": users,
            "search_query": search_query,
            "media": self.media,
        }
        return render(request, self.change_list_template, context)

    def user_messages_view(self, request, user_id):
        user = get_object_or_404(User.objects.select_related("profile"), pk=user_id)
        messages = (
            Message.objects.filter(sender=user)
            .select_related(
                "conversation",
                "conversation__match",
                "conversation__match__user1",
                "conversation__match__user2",
                "conversation__match__user1__profile",
                "conversation__match__user2__profile",
            )
            .order_by("-timestamp")
        )

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": f"Messages by {user.username}",
            "user_obj": user,
            "messages": messages,
            "back_url": reverse("admin:chat_message_changelist"),
            "media": self.media,
        }
        return render(request, "admin/chat/message/user_messages.html", context)
