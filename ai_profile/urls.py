from django.urls import path

from ai_profile.views import ProfileGenerateView

urlpatterns = [
    path("generate/", ProfileGenerateView.as_view(), name="ai_profile_generate"),
]
