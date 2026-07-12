from django.urls import path

from update.views import (
    AppVersionCheckView,
    AppVersionDownloadTrackView,
    AppVersionHistoryView,
    AppVersionPublishView,
)

urlpatterns = [
    path("version/", AppVersionCheckView.as_view(), name="app-version-check"),
    path("version/history/", AppVersionHistoryView.as_view(), name="app-version-history"),
    path("version/download/", AppVersionDownloadTrackView.as_view(), name="app-version-download-track"),
    path("version/publish/", AppVersionPublishView.as_view(), name="app-version-publish"),
]
