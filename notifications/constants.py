"""Notification type constants and preference mapping."""

from __future__ import annotations

# FCM / inbox notification types
CHAT_MESSAGE = "chat_message"
MESSAGE_REACTION = "message_reaction"
NEW_MATCH = "new_match"
PROFILE_LIKE = "profile_like"
SUPER_LIKE = "super_like"
PROFILE_VIEWED = "profile_viewed"
PROFILE_VERIFIED = "profile_verified"
PHOTO_APPROVED = "photo_approved"
SUBSCRIPTION_PURCHASED = "subscription_purchased"
SUBSCRIPTION_EXPIRED = "subscription_expired"
PAYMENT_SUCCESS = "payment_success"
PAYMENT_FAILURE = "payment_failure"
ADMIN_ANNOUNCEMENT = "admin_announcement"
SYSTEM_MAINTENANCE = "system_maintenance"
VERIFICATION_UPDATE = "verification_update"
MARKETING = "marketing"
SECURITY_ALERT = "security_alert"
CALL_INCOMING = "call_incoming"
CALL_MISSED = "call_missed"

ALL_TYPES = {
    CHAT_MESSAGE,
    MESSAGE_REACTION,
    NEW_MATCH,
    PROFILE_LIKE,
    SUPER_LIKE,
    PROFILE_VIEWED,
    PROFILE_VERIFIED,
    PHOTO_APPROVED,
    SUBSCRIPTION_PURCHASED,
    SUBSCRIPTION_EXPIRED,
    PAYMENT_SUCCESS,
    PAYMENT_FAILURE,
    ADMIN_ANNOUNCEMENT,
    SYSTEM_MAINTENANCE,
    VERIFICATION_UPDATE,
    MARKETING,
    SECURITY_ALERT,
    CALL_INCOMING,
    CALL_MISSED,
}

# Maps notification type → preference field on NotificationPreference
PREFERENCE_FIELD_BY_TYPE: dict[str, str] = {
    CHAT_MESSAGE: "chat_enabled",
    MESSAGE_REACTION: "chat_enabled",
    NEW_MATCH: "match_enabled",
    PROFILE_LIKE: "likes_enabled",
    SUPER_LIKE: "likes_enabled",
    PROFILE_VIEWED: "likes_enabled",
    PROFILE_VERIFIED: "verification_enabled",
    PHOTO_APPROVED: "verification_enabled",
    VERIFICATION_UPDATE: "verification_enabled",
    SUBSCRIPTION_PURCHASED: "payment_enabled",
    SUBSCRIPTION_EXPIRED: "payment_enabled",
    PAYMENT_SUCCESS: "payment_enabled",
    PAYMENT_FAILURE: "payment_enabled",
    ADMIN_ANNOUNCEMENT: "announcements_enabled",
    SYSTEM_MAINTENANCE: "announcements_enabled",
    MARKETING: "marketing_enabled",
    CALL_INCOMING: "calls_enabled",
    CALL_MISSED: "calls_enabled",
}
