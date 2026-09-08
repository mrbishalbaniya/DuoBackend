from django.urls import path

from photo_verification.views import (
    MyProfilePhotosView,
    PhotoAnalysisDetailView,
    PhotoDeleteView,
    PhotoReorderView,
    PhotoSetPrimaryView,
    PhotoUploadView,
)

urlpatterns = [
    path("upload/", PhotoUploadView.as_view(), name="photo-upload"),
    path("mine/", MyProfilePhotosView.as_view(), name="photo-mine"),
    path("reorder/", PhotoReorderView.as_view(), name="photo-reorder"),
    path("<int:pk>/set-primary/", PhotoSetPrimaryView.as_view(), name="photo-set-primary"),
    path("<int:pk>/", PhotoDeleteView.as_view(), name="photo-delete"),
    path("analysis/<int:pk>/", PhotoAnalysisDetailView.as_view(), name="photo-analysis-detail"),
]
