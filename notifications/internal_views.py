"""Internal endpoints called by chat-service to trigger push notifications.

chat-service owns message/reaction rows in its own database now, so it can't
hand this app a message_id to look up — it sends everything the push needs
directly. See chat-service/README.md and notifications/workers.py's
execute_chat_service_message_push / execute_chat_service_reaction_push.
"""

from __future__ import annotations

from rest_framework.response import Response
from rest_framework.views import APIView

from duo_project.security.internal_auth import ChatServiceTokenPermission
from duo_project.tasks.enqueue import safe_delay
from notifications import tasks as notification_tasks


class ChatServiceMessagePushView(APIView):
    authentication_classes = []
    permission_classes = [ChatServiceTokenPermission]

    def post(self, request):
        safe_delay(notification_tasks.send_chat_service_message_push_task, request.data)
        return Response({"status": "ok"})


class ChatServiceReactionPushView(APIView):
    authentication_classes = []
    permission_classes = [ChatServiceTokenPermission]

    def post(self, request):
        safe_delay(notification_tasks.send_chat_service_reaction_push_task, request.data)
        return Response({"status": "ok"})
