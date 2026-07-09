from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .defaults import merge_avatar_config
from .models import AvatarConfig


class AvatarBatchView(APIView):
    """Load avatar configs for many users in one request (globe / friends)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Avatars"])
    def post(self, request):
        raw_ids = request.data.get("user_ids") or []
        if not isinstance(raw_ids, list):
            return Response({"detail": "user_ids must be a list"}, status=400)
        ids = []
        for value in raw_ids[:200]:
            try:
                ids.append(int(value))
            except (TypeError, ValueError):
                continue
        if not ids:
            return Response({"configs": {}})

        rows = AvatarConfig.objects.filter(user_id__in=ids).only("user_id", "config")
        configs = {str(row.user_id): merge_avatar_config(row.config) for row in rows}
        return Response({"configs": configs})
