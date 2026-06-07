from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from .serializers import RegisterSerializer, UserSerializer, ProfileSerializer
from .models import Profile
from matching.models import Swipe


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)


class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class MyProfileView(APIView):
    def get(self, request):
        return Response(ProfileSerializer(request.user.profile).data)

    def put(self, request):
        serializer = ProfileSerializer(request.user.profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class DiscoverView(APIView):
    """Get profiles to swipe on (excludes self and already-swiped profiles)."""
    def get(self, request):
        swiped_ids = Swipe.objects.filter(
            from_user=request.user
        ).values_list('to_user_id', flat=True)
        profiles = Profile.objects.exclude(
            user=request.user
        ).exclude(
            user_id__in=swiped_ids
        ).filter(
            is_onboarded=True
        ).order_by('?')[:10]
        return Response(ProfileSerializer(profiles, many=True).data)


class ProfileDetailView(generics.RetrieveAPIView):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
