from django.urls import path
from .views import MyProfileView, DiscoverView, ProfileDetailView

urlpatterns = [
    path('me/', MyProfileView.as_view(), name='my_profile'),
    path('discover/', DiscoverView.as_view(), name='discover'),
    path('<int:pk>/', ProfileDetailView.as_view(), name='profile_detail'),
]
