from __future__ import annotations

from django.core.signing import TimestampSigner
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from calls.models import CallSession
from calls.serializers import CallSessionSerializer, InitiateCallSerializer
from calls.throttling import CallRateThrottle
from calls.services import (
    accept_call,
    cancel_call,
    get_call_for_user,
    get_ice_servers,
    hangup_call,
    initiate_call,
    mark_busy,
    reject_call,
    serialize_call,
)
from chat.views import get_user_conversation


class IceServersView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Calls"],
        summary="Get WebRTC ICE servers (STUN/TURN)",
        responses={200: OpenApiResponse(description='{"ice_servers": [...]}')},
    )
    def get(self, request):
        return Response({"ice_servers": get_ice_servers()})


class CallListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [CallRateThrottle]

    @extend_schema(
        tags=["Calls"],
        summary="Initiate a voice or video call",
        request=InitiateCallSerializer,
        responses={201: CallSessionSerializer},
    )
    def post(self, request):
        serializer = InitiateCallSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        convo, error = get_user_conversation(serializer.validated_data["conversation_id"], request.user)
        if error:
            return error

        call, reason = initiate_call(
            user=request.user,
            conversation=convo,
            call_type=serializer.validated_data["call_type"],
        )
        if not call:
            return Response({"detail": reason}, status=status.HTTP_409_CONFLICT)

        data = serialize_call(call, viewer_id=request.user.id)
        data["ice_servers"] = get_ice_servers()
        return Response(data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=["Calls"],
        summary="List recent calls for a conversation",
    )
    def get(self, request):
        conversation_id = request.query_params.get("conversation_id")
        if not conversation_id:
            return Response({"detail": "conversation_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        convo, error = get_user_conversation(conversation_id, request.user)
        if error:
            return error
        calls = (
            CallSession.objects.filter(conversation=convo)
            .select_related("conversation", "caller", "callee")
            .order_by("-started_at")[:50]
        )
        return Response(
            {
                "calls": [serialize_call(c, viewer_id=request.user.id) for c in calls],
            }
        )


class CallDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Calls"], summary="Get call session details")
    def get(self, request, call_id):
        call, reason = get_call_for_user(call_id, request.user)
        if not call:
            return Response({"detail": reason}, status=status.HTTP_404_NOT_FOUND)
        data = serialize_call(call, viewer_id=request.user.id)
        data["ice_servers"] = get_ice_servers()
        return Response(data)


class CallAcceptView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Calls"], summary="Accept incoming call")
    def post(self, request, call_id):
        call, reason = get_call_for_user(call_id, request.user)
        if not call:
            return Response({"detail": reason}, status=status.HTTP_404_NOT_FOUND)
        call, reason = accept_call(user=request.user, call=call)
        if not call:
            return Response({"detail": reason}, status=status.HTTP_409_CONFLICT)
        data = serialize_call(call, viewer_id=request.user.id)
        data["ice_servers"] = get_ice_servers()
        return Response(data)


class CallRejectView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Calls"], summary="Reject incoming call")
    def post(self, request, call_id):
        call, reason = get_call_for_user(call_id, request.user)
        if not call:
            return Response({"detail": reason}, status=status.HTTP_404_NOT_FOUND)
        call, reason = reject_call(user=request.user, call=call)
        if not call:
            return Response({"detail": reason}, status=status.HTTP_409_CONFLICT)
        return Response(serialize_call(call, viewer_id=request.user.id))


class CallBusyView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Calls"], summary="Decline call because busy")
    def post(self, request, call_id):
        call, reason = get_call_for_user(call_id, request.user)
        if not call:
            return Response({"detail": reason}, status=status.HTTP_404_NOT_FOUND)
        call, reason = mark_busy(user=request.user, call=call)
        if not call:
            return Response({"detail": reason}, status=status.HTTP_409_CONFLICT)
        return Response(serialize_call(call, viewer_id=request.user.id))


class CallCancelView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Calls"], summary="Cancel outgoing ringing call")
    def post(self, request, call_id):
        call, reason = get_call_for_user(call_id, request.user)
        if not call:
            return Response({"detail": reason}, status=status.HTTP_404_NOT_FOUND)
        call, reason = cancel_call(user=request.user, call=call)
        if not call:
            return Response({"detail": reason}, status=status.HTTP_409_CONFLICT)
        return Response(serialize_call(call, viewer_id=request.user.id))


class CallHangupView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Calls"], summary="End active call")
    def post(self, request, call_id):
        call, reason = get_call_for_user(call_id, request.user)
        if not call:
            return Response({"detail": reason}, status=status.HTTP_404_NOT_FOUND)
        call, reason = hangup_call(user=request.user, call=call)
        if not call:
            return Response({"detail": reason}, status=status.HTTP_409_CONFLICT)
        return Response(serialize_call(call, viewer_id=request.user.id))


class CallWebSocketTicketView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [CallRateThrottle]

    @extend_schema(
        tags=["Calls"],
        summary="Get WebSocket ticket for call signaling",
        responses={200: OpenApiResponse(description='{"ticket": "..."}')},
    )
    def post(self, request, conversation_id):
        convo, error = get_user_conversation(conversation_id, request.user)
        if error:
            return error

        signer = TimestampSigner(salt="duo-call-ws-ticket")
        ticket = signer.sign(f"{request.user.id}:{convo.public_id}")
        return Response({"ticket": ticket})
