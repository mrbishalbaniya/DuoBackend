from django.urls import path

from .batch import AvatarBatchView
from .views import (
    AvatarOutfitDetailView,
    AvatarOutfitListCreateView,
    MyAvatarView,
    PublicAvatarView,
)

urlpatterns = [
    path("me/", MyAvatarView.as_view(), name="avatar-me"),
    path("batch/", AvatarBatchView.as_view(), name="avatar-batch"),
    path("outfits/", AvatarOutfitListCreateView.as_view(), name="avatar-outfits"),
    path("outfits/<int:pk>/", AvatarOutfitDetailView.as_view(), name="avatar-outfit-detail"),
    path("users/<int:user_id>/", PublicAvatarView.as_view(), name="avatar-public"),
]
