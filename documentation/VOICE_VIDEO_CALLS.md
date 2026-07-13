# Voice & Video Calling

Production-ready WebRTC calling for matched Duo users across Django, Flutter, and Next.js.

## Architecture

```
Caller App                    Django Backend                     Callee App
    |                              |                                |
    |-- POST /api/calls/ --------->| Create CallSession (ringing)     |
    |                              |-- inbox: call_incoming --------->|
    |                              |-- FCM: call_incoming ----------->|
    |-- ws/call/{convo}/?ticket -->|                                |
    |-- call_offer (SDP) --------->|-- relay ----------------------->|
    |<-- call_answer (SDP) --------|<-- call_answer ------------------|
    |<=========== WebRTC media (P2P via STUN/TURN) =================>|
    |-- POST hangup -------------->| Update CallSession (ended)       |
```

## Signaling events (WebSocket `ws/call/<conversation_id>/`)

| Event | Direction | Purpose |
|-------|-----------|---------|
| `call_invite` | Client → Server → Peer | Optional re-invite |
| `call_accept` | Client → Server → Peer | Callee accepted (REST also available) |
| `call_reject` | Client → Server → Peer | Decline |
| `call_busy` | Client → Server → Peer | Busy signal |
| `call_cancel` | Client → Server → Peer | Caller cancelled while ringing |
| `call_hangup` | Client → Server → Peer | End active call |
| `call_offer` | Client → Server → Peer | WebRTC SDP offer |
| `call_answer` | Client → Server → Peer | WebRTC SDP answer |
| `ice_candidate` | Client → Server → Peer | ICE trickle |
| `call_reconnect` | Client → Server → Peer | Reconnection hint |
| `call_quality` | Client → Server → Peer | Quality telemetry |

Inbox events (`ws/inbox/`):

| Event | Purpose |
|-------|---------|
| `call_incoming` | Ring UI when app is foreground |
| `call_accepted` | Peer accepted |
| `call_ended` / `call_missed` / `call_rejected` | Terminal states |

## REST API (additive)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/calls/ice-servers/` | STUN/TURN config |
| POST | `/api/calls/` | Initiate call |
| GET | `/api/calls/?conversation_id=` | Call history |
| GET | `/api/calls/{id}/` | Call status |
| POST | `/api/calls/{id}/accept/` | Accept |
| POST | `/api/calls/{id}/reject/` | Reject |
| POST | `/api/calls/{id}/busy/` | Busy |
| POST | `/api/calls/{id}/cancel/` | Cancel outgoing |
| POST | `/api/calls/{id}/hangup/` | End call |
| POST | `/api/calls/conversations/{id}/ws-ticket/` | Signaling WS ticket |

## Security

- Only matched conversation participants can call
- Blocked users cannot call
- JWT or signed WS ticket auth (300s TTL)
- Rate limits on signaling events
- One active call per user (busy detection)
- 45s ring timeout → missed call

## STUN/TURN environment variables

```env
WEBRTC_STUN_URLS=stun:stun.l.google.com:19302
WEBRTC_TURN_URL=turn:turn.example.com:3478
WEBRTC_TURN_USERNAME=
WEBRTC_TURN_CREDENTIAL=
WEBRTC_TURN_SECRET=          # coturn static auth secret
WEBRTC_TURN_TTL=86400
```

## Deploy

```bash
python manage.py migrate   # calls + notifications.calls_enabled
```

## Clients

- **Flutter:** `features/call/` — `flutter_webrtc`, global `CallBridge`, chat header buttons
- **Next.js:** `lib/call/`, `components/call/CallBridge`, chat header buttons
- **Push:** `call_incoming`, `call_missed` FCM types with deep link `/chat?conversation=…&call=…`
