from django.urls import path
from .views import (
    ConversationListView,
    MessageListView,
    MessageDeleteView,
    MessageReactView,
    ConversationDetailView,
    TypingHeartbeatView,
    ImageUploadView,
    ConversationSettingsView,
    ConversationClearHistoryView,
    ConversationUnmatchView,
    ConversationReportView,
    ConversationSecurityEventView,
    WebSocketTicketView,
)

# conversation_id accepts 10-digit public_id (or legacy short pk).
urlpatterns = [
    path('conversations/', ConversationListView.as_view(), name='conversation_list'),
    path('conversations/<str:conversation_id>/', ConversationDetailView.as_view(), name='conversation_detail'),
    path('conversations/<str:conversation_id>/settings/', ConversationSettingsView.as_view(), name='conversation_settings'),
    path('conversations/<str:conversation_id>/security-events/', ConversationSecurityEventView.as_view(), name='conversation_security_events'),
    path('conversations/<str:conversation_id>/clear/', ConversationClearHistoryView.as_view(), name='conversation_clear'),
    path('conversations/<str:conversation_id>/unmatch/', ConversationUnmatchView.as_view(), name='conversation_unmatch'),
    path('conversations/<str:conversation_id>/report/', ConversationReportView.as_view(), name='conversation_report'),
    path('conversations/<str:conversation_id>/messages/', MessageListView.as_view(), name='messages'),
    path('conversations/<str:conversation_id>/typing/', TypingHeartbeatView.as_view(), name='typing_heartbeat'),
    path('conversations/<str:conversation_id>/ws-ticket/', WebSocketTicketView.as_view(), name='ws_ticket'),
    path('messages/<int:message_id>/delete/', MessageDeleteView.as_view(), name='message_delete'),
    path('messages/<int:message_id>/react/', MessageReactView.as_view(), name='message_react'),
    path('upload/', ImageUploadView.as_view(), name='image_upload'),
]
