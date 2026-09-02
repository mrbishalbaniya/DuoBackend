from django.urls import path

from .views import SupportRequestCreateView

urlpatterns = [
    path("requests/", SupportRequestCreateView.as_view(), name="support_request_create"),
]
