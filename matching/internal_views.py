"""Internal endpoint chat-service calls to perform an authoritative unmatch.

Match/Swipe rows are monolith-owned data — chat-service never writes them
directly, it asks the monolith to do so here. Deleting the Match fires the
existing `on_match_deleted` signal (duo_project/realtime/signals.py), which
tells chat-service to drop its shadow copy of the match/conversation.
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from duo_project.security.internal_auth import ChatServiceTokenPermission
from matching.models import Match, Swipe


class UnmatchView(APIView):
    authentication_classes = []
    permission_classes = [ChatServiceTokenPermission]

    def post(self, request):
        match_id = request.data.get("match_id")
        user_id = request.data.get("user_id")
        other_user_id = request.data.get("other_user_id")
        if not all([match_id, user_id, other_user_id]):
            return Response({"detail": "match_id, user_id, other_user_id are required."}, status=status.HTTP_400_BAD_REQUEST)

        match = Match.objects.filter(id=match_id).first()
        if not match:
            return Response({"status": "ok"})  # already gone — idempotent

        if {match.user1_id, match.user2_id} != {int(user_id), int(other_user_id)}:
            return Response({"detail": "Match does not involve the given users."}, status=status.HTTP_400_BAD_REQUEST)

        Swipe.objects.update_or_create(
            from_user_id=user_id, to_user_id=other_user_id, defaults={"action": "SKIP"},
        )
        Swipe.objects.update_or_create(
            from_user_id=other_user_id, to_user_id=user_id, defaults={"action": "SKIP"},
        )
        match.delete()
        return Response({"status": "ok"})
