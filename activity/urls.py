from django.urls import path

from .views import ActivityZonesView

urlpatterns = [
    path("zones/", ActivityZonesView.as_view(), name="activity-zones"),
]
