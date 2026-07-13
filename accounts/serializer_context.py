"""Serializer context helpers for accounts."""

from __future__ import annotations

from subscriptions.billing_context import build_profile_billing_context, ensure_viewer_wallet_in_context


def profile_list_serializer_context(request, profiles) -> dict:
    """Build DRF serializer context with batched billing data for a profile list."""
    user_ids = [profile.user_id for profile in profiles]
    billing = build_profile_billing_context(user_ids)
    billing = ensure_viewer_wallet_in_context(billing, request.user)
    return {
        "request": request,
        "profile_billing": billing,
    }
