from django.urls import re_path

from calls.consumers import CallSignalingConsumer

websocket_urlpatterns = [
    re_path(r"ws/call/(?P<conversation_id>[^/]+)/$", CallSignalingConsumer.as_asgi()),
]
