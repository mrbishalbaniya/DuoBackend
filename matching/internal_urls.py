from django.urls import path

from matching.internal_views import UnmatchView

urlpatterns = [
    path("unmatch/", UnmatchView.as_view(), name="internal-unmatch"),
]
