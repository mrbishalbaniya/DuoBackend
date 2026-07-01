from django.urls import path
from .views import MyProfileView, DiscoverView, ProfileDetailView, ProfilePhotoUploadView, ProfileVisitRecordView

urlpatterns = [
    path('me/', MyProfileView.as_view(), name='my_profile'),
    path('me/upload-photo/', ProfilePhotoUploadView.as_view(), name='profile_photo_upload'),
    path('discover/', DiscoverView.as_view(), name='discover'),
    path('<int:pk>/visit/', ProfileVisitRecordView.as_view(), name='profile_visit'),
    path('<int:pk>/', ProfileDetailView.as_view(), name='profile_detail'),
]
