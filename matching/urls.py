from django.urls import path
from .views import (
    LikeQuotaView,
    RewindView,
    SwipeView,
    UnlikeView,
    MatchListView,
    MatchInsightView,
    LikedByYouView,
    LikesYouView,
    ProfileVisitorsView,
    SkippedByYouView,
)

urlpatterns = [
    path('swipe/', SwipeView.as_view(), name='swipe'),
    path('likes/quota/', LikeQuotaView.as_view(), name='like_quota'),
    path('unlike/', UnlikeView.as_view(), name='unlike'),
    path('rewind/', RewindView.as_view(), name='rewind'),
    path('matches/', MatchListView.as_view(), name='match_list'),
    path('liked-by-you/', LikedByYouView.as_view(), name='liked_by_you'),
    path('likes-you/', LikesYouView.as_view(), name='likes_you'),
    path('profile-visitors/', ProfileVisitorsView.as_view(), name='profile_visitors'),
    path('skipped-by-you/', SkippedByYouView.as_view(), name='skipped_by_you'),
    path('insights/<int:pk>/', MatchInsightView.as_view(), name='match_insight'),
]
