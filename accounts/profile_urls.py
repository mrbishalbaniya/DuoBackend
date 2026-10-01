from django.urls import path
from .views import MyProfileView, DiscoverView, ProfileDetailView, ProfilePhotoUploadView, ProfileVisitRecordView, ProfileLookupsView, ProfileWritingSuggestionsView
from .location_views import LiveLocationView

urlpatterns = [
    path('me/', MyProfileView.as_view(), name='my_profile'),
    path('me/location/', LiveLocationView.as_view(), name='live_location'),
    path('me/upload-photo/', ProfilePhotoUploadView.as_view(), name='profile_photo_upload'),
    path('me/writing-suggestions/', ProfileWritingSuggestionsView.as_view(), name='profile_writing_suggestions'),
    path('lookups/', ProfileLookupsView.as_view(), name='profile_lookups'),
    path('discover/', DiscoverView.as_view(), name='discover'),
    path('<int:pk>/visit/', ProfileVisitRecordView.as_view(), name='profile_visit'),
    path('<int:pk>/', ProfileDetailView.as_view(), name='profile_detail'),
]
