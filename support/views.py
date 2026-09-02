from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from .serializers import SupportRequestCreateSerializer


class SupportRequestCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Support"],
        summary="Submit a support request or bug report",
        request=SupportRequestCreateSerializer,
    )
    def post(self, request):
        serializer = SupportRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        support_request = serializer.save(
            user=request.user,
            contact_email=serializer.validated_data.get("contact_email") or request.user.email,
        )
        return Response(
            {
                "id": support_request.id,
                "detail": "Thanks — we've received your message and will get back to you soon.",
            },
            status=status.HTTP_201_CREATED,
        )
