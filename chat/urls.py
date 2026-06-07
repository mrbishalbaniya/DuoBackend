from django.urls import path
from .views import ConversationListView, MessageListView, ConversationDetailView, TypingHeartbeatView, ImageUploadView

urlpatterns = [
    path('conversations/', ConversationListView.as_view(), name='conversation_list'),
    path('conversations/<int:conversation_id>/', ConversationDetailView.as_view(), name='conversation_detail'),
    path('conversations/<int:conversation_id>/messages/', MessageListView.as_view(), name='messages'),
    path('conversations/<int:conversation_id>/typing/', TypingHeartbeatView.as_view(), name='typing_heartbeat'),
    path('upload/', ImageUploadView.as_view(), name='image_upload'),
]
