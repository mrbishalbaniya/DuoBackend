from django.urls import path
from .views import SwipeView, MatchListView, MatchInsightView

urlpatterns = [
    path('swipe/', SwipeView.as_view(), name='swipe'),
    path('matches/', MatchListView.as_view(), name='match_list'),
    path('insights/<int:pk>/', MatchInsightView.as_view(), name='match_insight'),
]
