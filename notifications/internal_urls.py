from django.urls import path

from notifications.internal_views import ChatServiceMessagePushView, ChatServiceReactionPushView

urlpatterns = [
    path("chat-message/", ChatServiceMessagePushView.as_view(), name="internal-chat-message-push"),
    path("chat-reaction/", ChatServiceReactionPushView.as_view(), name="internal-chat-reaction-push"),
]
