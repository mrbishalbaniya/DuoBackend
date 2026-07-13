# Duo WebSocket API

Production real-time API for chat, inbox events, activity map, and analytics.

**Authentication:** JWT access token via one of:

- Query: `?token=<access_jwt>`
- Header: `Authorization: Bearer <access_jwt>`
- Cookie: `duo_access=<access_jwt>`
- Chat only: signed ticket `?ticket=<ws_ticket>` from `POST /api/chat/conversations/{id}/ws-ticket/`

**Close codes:** `4401` unauthenticated, `4403` forbidden (not a conversation member), `4429` too many connections (max 12 per user).

---

## Routes

| Route | Purpose |
|-------|---------|
| `ws/chat/<conversation_id>/` | Per-conversation messaging |
| `ws/inbox/` | User-level events (matches, likes, notifications) |
| `ws/activity/` | Live activity heatmap zones |
| `ws/analytics/` | Staff analytics stream |

`conversation_id` is the 10-digit **public_id** (same as REST/Flutter).

---

## Chat (`ws/chat/<conversation_id>/`)

### Client → Server

| type | Payload | Notes |
|------|---------|-------|
| `ping` | `{ "type": "ping", "ts": 123 }` | Heartbeat |
| `chat_message` | `content`, `image_url?`, `reply_to_id?`, `client_temp_id?` | Send message |
| `edit_message` | `id`, `content` | Edit own message |
| `delete_message` | `id`, `delete_type`: `for_me` \| `for_everyone` | Delete |
| `message_reaction` | `id`, `emoji` | Toggle reaction |
| `typing` | `is_typing`: bool | Throttled (8/10s) |
| `recording` | `is_recording`: bool | Voice/video recording indicator |
| `upload_progress` | `upload_id`, `progress`, `media_type` | Relay only (image/voice/video) |
| `mark_read` | — | Mark incoming messages read |
| `security_event` | `event_code` | Screenshot/recording system messages |

### Server → Client

| type | Payload |
|------|---------|
| `connected` | `{ conversation_id }` |
| `pong` | `{ ts }` |
| `ping` | Server heartbeat every 30s |
| `chat_message` | `id`, `content`, `image_url`, `sender_id`, `sender_name`, `timestamp`, `message_type`, `reply_to?`, `client_temp_id?`, `event_code?` |
| `message_ack` | `{ id, client_temp_id, status: "sent" }` |
| `messages_delivered` | `{ recipient_id, message_ids[] }` |
| `messages_read` | `{ reader_id, message_ids[] }` |
| `typing_status` | `{ user_id, is_typing }` |
| `recording_status` | `{ user_id, is_recording }` |
| `upload_progress` | `{ user_id, upload_id, progress, media_type }` |
| `message_edited` | `{ id, content, edited_at, sender_id }` |
| `message_deleted` | `{ id, user_id, delete_type }` |
| `message_reacted` | `{ id, user_id, emoji, reactions }` |
| `error` | `{ code, message }` |

**Backward compatible:** Existing Flutter/Next.js handlers for `chat_message`, `typing_status`, `messages_read`, `message_deleted`, `message_reacted` are unchanged.

---

## Inbox (`ws/inbox/`)

Single socket per user for app-wide real-time events. **Optional** — clients can adopt incrementally; REST + FCM continue to work.

### Client → Server

| type | Payload |
|------|---------|
| `ping` | `{ ts? }` |
| `presence_get` | `{ user_id? }` |
| `presence_subscribe` | `{ status?: "online" }` |

### Server → Client

| type | Payload |
|------|---------|
| `connected` | `{ user_id, presence }` |
| `match_created` | `{ match_id, other_user_id, compatibility_score, conversation_id, matched_at }` |
| `like_received` | `{ from_user_id, action }` |
| `superlike_received` | `{ from_user_id, action }` |
| `profile_viewed` | `{ viewer_id }` |
| `conversation_updated` | `{ conversation_id, last_message }` |
| `notification` | `{ title, body, data }` |
| `subscription_updated` | `{ is_premium, expires_at }` |
| `compatibility_updated` | `{ match_id, compatibility_score, user1_id, user2_id }` |
| `profile_verified` | `{ verified: true }` |
| `presence_update` | `{ user_id, status, last_seen }` |
| `error` | `{ code, message }` |

---

## Activity (`ws/activity/`)

### Client → Server

| type | Payload |
|------|---------|
| `ping` | `{ ts? }` |
| `viewport` | `lat_min`, `lat_max`, `lon_min`, `lon_max`, `zoom`, flags: `trending`, `events`, `friends`, `nearby`, `user_lat`, `user_lng`, `nearby_km` |

### Server → Client

| type | Payload |
|------|---------|
| `connected` | — |
| `zones` | `{ zones: [...] }` |
| `pong` | `{ ts }` |

Map refreshes automatically on swipes, matches, messages, and profile visits.

---

## Security

- JWT validated on every connection
- Chat ticket bound to `user_id:conversation_id`, 5-minute TTL
- Room membership verified before join
- Per-user event rate limits (Redis)
- Message sender verified server-side (no spoofing)
- Errors return `{ type: "error", code, message }` without crashing the socket

---

## Reconnect

Clients should use exponential backoff (Flutter/Next.js already implement this). Server sends `ping` every 30s; clients may respond with `{ type: "ping" }` → `{ type: "pong" }`.

---

## Redis groups

| Group | Members |
|-------|---------|
| `chat_{conversation_id}` | Conversation participants |
| `user_{user_id}` | Inbox + chat sockets for user |
| `activity_feed` | Map clients |

---

## Future (not yet in clients)

- `forward_message` — forward via REST duplicate + WS broadcast
- `pin_message` — use conversation settings REST
- Invisible presence mode
