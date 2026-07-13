from django.urls import path

from calls.views import (
    CallAcceptView,
    CallBusyView,
    CallCancelView,
    CallDetailView,
    CallHangupView,
    CallListCreateView,
    CallRejectView,
    CallWebSocketTicketView,
    IceServersView,
)

urlpatterns = [
    path("ice-servers/", IceServersView.as_view(), name="calls-ice-servers"),
    path(
        "conversations/<str:conversation_id>/ws-ticket/",
        CallWebSocketTicketView.as_view(),
        name="calls-ws-ticket",
    ),
    path("", CallListCreateView.as_view(), name="calls-list-create"),
    path("<str:call_id>/accept/", CallAcceptView.as_view(), name="calls-accept"),
    path("<str:call_id>/reject/", CallRejectView.as_view(), name="calls-reject"),
    path("<str:call_id>/busy/", CallBusyView.as_view(), name="calls-busy"),
    path("<str:call_id>/cancel/", CallCancelView.as_view(), name="calls-cancel"),
    path("<str:call_id>/hangup/", CallHangupView.as_view(), name="calls-hangup"),
    path("<str:call_id>/", CallDetailView.as_view(), name="calls-detail"),
]
