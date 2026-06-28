from django.urls import path
from .views import (
    ConversationListView,
    MessageListView,
    ConversationDetailView,
    TypingHeartbeatView,
    ImageUploadView,
    ConversationSettingsView,
    ConversationClearHistoryView,
    ConversationUnmatchView,
    ConversationReportView,
)

urlpatterns = [
    path('conversations/', ConversationListView.as_view(), name='conversation_list'),
    path('conversations/<int:conversation_id>/', ConversationDetailView.as_view(), name='conversation_detail'),
    path('conversations/<int:conversation_id>/settings/', ConversationSettingsView.as_view(), name='conversation_settings'),
    path('conversations/<int:conversation_id>/clear/', ConversationClearHistoryView.as_view(), name='conversation_clear'),
    path('conversations/<int:conversation_id>/unmatch/', ConversationUnmatchView.as_view(), name='conversation_unmatch'),
    path('conversations/<int:conversation_id>/report/', ConversationReportView.as_view(), name='conversation_report'),
    path('conversations/<int:conversation_id>/messages/', MessageListView.as_view(), name='messages'),
    path('conversations/<int:conversation_id>/typing/', TypingHeartbeatView.as_view(), name='typing_heartbeat'),
    path('upload/', ImageUploadView.as_view(), name='image_upload'),
]
