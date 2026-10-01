"""Sample data for admin previews, so every template renders like a real email."""

from __future__ import annotations

from email_service.constants import EmailEvent

_RECEIPT_DETAILS = [
    {"label": "Coins added", "value": "500 coins"},
    {"label": "New balance", "value": "1,250 coins"},
    {"label": "Paid", "value": "NPR 500"},
    {"label": "Paid with", "value": "eSewa"},
    {"label": "Reference", "value": "TOPUP-8F2A91"},
    {"label": "Date", "value": "Sep 29, 2026"},
]

SAMPLE_CONTEXT: dict[str, dict] = {
    EmailEvent.WELCOME: {"user_name": "Aarati"},
    EmailEvent.SUBSCRIPTION_CONFIRMED: {
        "user_name": "Aarati",
        "plan_name": "Who Liked You · 30 days",
        "title": "Who Liked You · 30 days is active",
        "intro": "Thank you! Your payment went through and your perks are ready to use.",
        "details": [
            {"label": "Plan", "value": "Who Liked You · 30 days"},
            {"label": "Amount", "value": "NPR 499"},
            {"label": "Paid with", "value": "eSewa"},
            {"label": "Active until", "value": "Oct 29, 2026"},
            {"label": "Reference", "value": "SUB-4C19E2"},
        ],
        "cta_label": "Open Duo",
        "cta_url": "#",
    },
    EmailEvent.SUBSCRIPTION_FAILED: {
        "user_name": "Aarati",
        "title": "Coin recharge failed",
        "intro": "Your eSewa payment didn't go through, so no coins were added. You haven't been charged.",
        "details": [
            {"label": "Coins", "value": "500 coins"},
            {"label": "Amount", "value": "NPR 500"},
            {"label": "Reference", "value": "TOPUP-8F2A91"},
        ],
        "cta_label": "Try again",
        "cta_url": "#",
    },
    EmailEvent.MATCH_NOTIFICATION: {
        "user_name": "Aarati",
        "match_name": "Rohan",
        "intro": "You and Rohan liked each other. Say hello while it's fresh.",
        "cta_label": "Message Rohan",
        "cta_url": "#",
        "message": "",
    },
    EmailEvent.ADMIN_ANNOUNCEMENT: {
        "user_name": "Aarati",
        "title": "Dashain offer: 20% extra coins",
        "message": "Happy Dashain! This week every coin recharge gets 20% extra coins.\n\nThe offer ends on Sunday.",
        "cta_label": "Recharge now",
        "cta_url": "#",
    },
    EmailEvent.ACCOUNT_STATUS: {
        "user_name": "Aarati",
        "title": "Your verified badge was removed",
        "intro": "Your profile photos changed, so your badge needs a fresh selfie check.",
        "note": "It takes under a minute. Your matches and chats are not affected.",
        "cta_label": "Verify again",
        "cta_url": "#",
        "message": "",
    },
    EmailEvent.GENERIC: {
        "user_name": "Aarati",
        "title": "Coins added to your wallet",
        "intro": "Your recharge was successful.",
        "details": _RECEIPT_DETAILS,
        "note": "Keep this email as your receipt.",
        "cta_label": "View my wallet",
        "cta_url": "#",
        "message": "",
    },
    EmailEvent.CONTACT_FORM: {
        "message": "Hi team, I can't upload my second photo. It says duplicate image. Thanks!",
    },
}


def sample_context(event: str) -> dict:
    return dict(SAMPLE_CONTEXT.get(event, {}))
