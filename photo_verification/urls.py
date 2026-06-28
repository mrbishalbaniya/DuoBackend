from django.urls import path

from photo_verification.views import PhotoAnalysisDetailView, PhotoUploadView

urlpatterns = [
    path("upload/", PhotoUploadView.as_view(), name="photo-upload"),
    path("analysis/<int:pk>/", PhotoAnalysisDetailView.as_view(), name="photo-analysis-detail"),
]
