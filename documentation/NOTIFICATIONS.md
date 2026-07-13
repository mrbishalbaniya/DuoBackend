# Push Notifications (FCM)

Production-grade Firebase Cloud Messaging for Duo across Django, Flutter, and Next.js.

## Architecture

```
Event (chat, match, like, payment, …)
  → notifications/dispatch.py (async thread)
  → notification_service.send_push_notification()
    → preference check
    → dedup (Redis, 30s)
    → skip if online (chat only)
    → FCMService.send_to_user() per device
    → PushDeliveryLog
    → WebSocket broadcast_notification()
```

## API Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/api/notifications/config/` | Public | Firebase client config |
| POST | `/api/notifications/devices/` | User | Register FCM token |
| POST | `/api/notifications/devices/unregister/` | User | Deactivate token |
| POST | `/api/notifications/devices/unregister-all/` | User | Logout cleanup |
| GET/PATCH | `/api/notifications/preferences/` | User | Notification prefs |
| POST | `/api/notifications/admin/broadcast/` | Admin | Broadcast push |

## Notification Types

- `chat_message`, `message_reaction`
- `new_match`, `profile_like`, `super_like`, `profile_viewed`
- `profile_verified`, `photo_approved`, `verification_update`
- `subscription_purchased`, `payment_success`, `payment_failure`
- `admin_announcement`, `system_maintenance`, `marketing`

## User Preferences

Stored in `NotificationPreference` (auto-created per user):

- Master: `push_enabled`
- Categories: chat, match, likes, marketing, announcements, verification, payment
- Device: sound, vibration

Conversation mute (`ConversationPreference.is_muted`) is respected for chat and reactions.

## Environment Variables

See `.env.example` — `FCM_ENABLED`, `FIREBASE_*`, `FCM_VAPID_KEY`, `FIREBASE_SERVICE_ACCOUNT_JSON`.

Admin → Integration settings overrides env when set.

## Admin

- **DeviceToken** — view active tokens
- **NotificationPreference** — per-user settings
- **PushDeliveryLog** — delivery audit + retry action
- **Admin broadcast API** — `POST /api/notifications/admin/broadcast/`

## Clients

- **Flutter**: `PushMessagingCoordinator`, local notifications, large icons, action buttons
- **Next.js**: `lib/push/fcm.ts`, service worker, Settings preferences sync

## Run Migration

```bash
python manage.py migrate notifications
```
