"""
ASGI config for duo_project project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "duo_project.settings")

from django.core.asgi import get_asgi_application

django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter

import chat.routing
import activity.routing
import analytics.routing
import calls.routing
import duo_project.realtime.routing as realtime_routing
from duo_project.channels_auth import JWTAuthMiddlewareStack

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": JWTAuthMiddlewareStack(
            URLRouter(
                chat.routing.websocket_urlpatterns
                + calls.routing.websocket_urlpatterns
                + realtime_routing.websocket_urlpatterns
                + activity.routing.websocket_urlpatterns
                + analytics.routing.websocket_urlpatterns
            )
        ),
    }
)
