from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .defaults import DEFAULT_AVATAR_CONFIG, merge_avatar_config
from .models import AvatarConfig, AvatarOutfit
from .serializers import AvatarConfigSerializer, AvatarOutfitSerializer
from duo_project.cache import api_cache
from duo_project.cache import keys as cache_keys
from duo_project.cache import ttl as cache_ttl
from duo_project.cache.invalidation import invalidate_avatar


class MyAvatarView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Avatars"])
    def get(self, request):
        cache_key = cache_keys.avatar(request.user.id)

        def build():
            try:
                row = AvatarConfig.objects.get(user=request.user)
                data = AvatarConfigSerializer(row).data
                data["config"] = merge_avatar_config(row.config)
                return data
            except AvatarConfig.DoesNotExist:
                return {
                    "config": dict(DEFAULT_AVATAR_CONFIG),
                    "version": 1,
                    "updated_at": None,
                }

        return Response(
            api_cache.get_or_set(cache_key, build, cache_ttl.PROFILE, label="avatar")
        )

    @extend_schema(tags=["Avatars"])
    def put(self, request):
        ser = AvatarConfigSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        config = ser.validated_data["config"]
        row, _ = AvatarConfig.objects.update_or_create(
            user=request.user,
            defaults={"config": config, "version": 1},
        )
        invalidate_avatar(request.user.id)
        return Response(AvatarConfigSerializer(row).data)

    @extend_schema(tags=["Avatars"])
    def patch(self, request):
        return self.put(request)

    @extend_schema(tags=["Avatars"])
    def delete(self, request):
        AvatarConfig.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AvatarOutfitListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Avatars"])
    def get(self, request):
        qs = AvatarOutfit.objects.filter(user=request.user)
        return Response(AvatarOutfitSerializer(qs, many=True).data)

    @extend_schema(tags=["Avatars"])
    def post(self, request):
        ser = AvatarOutfitSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        outfit = AvatarOutfit.objects.create(user=request.user, **ser.validated_data)
        return Response(AvatarOutfitSerializer(outfit).data, status=status.HTTP_201_CREATED)


class AvatarOutfitDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, request, pk):
        try:
            return AvatarOutfit.objects.get(pk=pk, user=request.user)
        except AvatarOutfit.DoesNotExist:
            return None

    @extend_schema(tags=["Avatars"])
    def put(self, request, pk):
        outfit = self._get(request, pk)
        if not outfit:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        ser = AvatarOutfitSerializer(outfit, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        for key, value in ser.validated_data.items():
            setattr(outfit, key, value)
        outfit.save()
        return Response(AvatarOutfitSerializer(outfit).data)

    @extend_schema(tags=["Avatars"])
    def delete(self, request, pk):
        outfit = self._get(request, pk)
        if not outfit:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        outfit.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PublicAvatarView(APIView):
    """Read another user's avatar config (for globe / friends)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Avatars"])
    def get(self, request, user_id: int):
        try:
            row = AvatarConfig.objects.get(user_id=user_id)
            return Response({"user_id": user_id, "config": merge_avatar_config(row.config)})
        except AvatarConfig.DoesNotExist:
            return Response({"user_id": user_id, "config": None})
