"""Minimal Stripe REST client for wallet top-ups (Checkout Sessions + webhook verification).

Uses the HTTP API directly (https://docs.stripe.com/api) so no extra dependency is needed.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from decimal import Decimal
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

STRIPE_API_BASE = "https://api.stripe.com/v1"
WEBHOOK_TOLERANCE_SECONDS = 300

# Currencies Stripe charges without a minor unit (https://docs.stripe.com/currencies#zero-decimal).
ZERO_DECIMAL_CURRENCIES = {
    "bif", "clp", "djf", "gnf", "jpy", "kmf", "krw", "mga",
    "pyg", "rwf", "ugx", "vnd", "vuv", "xaf", "xof", "xpf",
}


class StripeError(Exception):
    pass


def to_minor_units(amount: Decimal | int | str, currency: str) -> int:
    value = Decimal(str(amount))
    if currency.lower() in ZERO_DECIMAL_CURRENCIES:
        return int(value)
    return int((value * 100).quantize(Decimal("1")))


def from_minor_units(amount: int, currency: str) -> Decimal:
    if currency.lower() in ZERO_DECIMAL_CURRENCIES:
        return Decimal(amount)
    return (Decimal(amount) / 100).quantize(Decimal("0.01"))


def _flatten(params: dict[str, Any], prefix: str = "") -> list[tuple[str, str]]:
    """Encode nested dicts/lists the way Stripe expects (a[b][0][c]=v)."""
    items: list[tuple[str, str]] = []
    for key, value in params.items():
        full_key = f"{prefix}[{key}]" if prefix else str(key)
        if isinstance(value, dict):
            items.extend(_flatten(value, full_key))
        elif isinstance(value, (list, tuple)):
            for index, entry in enumerate(value):
                if isinstance(entry, dict):
                    items.extend(_flatten(entry, f"{full_key}[{index}]"))
                else:
                    items.append((f"{full_key}[{index}]", str(entry)))
        elif value is not None:
            if isinstance(value, bool):
                value = "true" if value else "false"
            items.append((full_key, str(value)))
    return items


def _request(method: str, path: str, secret_key: str, params: dict | None = None) -> dict:
    if not secret_key:
        raise StripeError("Stripe secret key is not configured.")
    url = f"{STRIPE_API_BASE}{path}"
    data = None
    if params and method == "POST":
        data = urlencode(_flatten(params)).encode("utf-8")
    elif params:
        url = f"{url}?{urlencode(_flatten(params))}"
    request = Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Stripe-Version": "2024-06-20",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8"))
            message = body.get("error", {}).get("message") or str(exc)
        except Exception:
            message = str(exc)
        raise StripeError(message) from exc
    except URLError as exc:
        raise StripeError(f"Could not reach Stripe: {exc.reason}") from exc


def create_checkout_session(
    *,
    secret_key: str,
    amount: Decimal | int,
    currency: str,
    product_name: str,
    reference: str,
    success_url: str,
    cancel_url: str,
    customer_email: str = "",
    metadata: dict[str, str] | None = None,
) -> dict:
    params: dict[str, Any] = {
        "mode": "payment",
        "client_reference_id": reference,
        "success_url": success_url,
        "cancel_url": cancel_url,
        "line_items": [
            {
                "quantity": 1,
                "price_data": {
                    "currency": currency.lower(),
                    "unit_amount": to_minor_units(amount, currency),
                    "product_data": {"name": product_name},
                },
            }
        ],
        "metadata": {"transaction_uuid": reference, **(metadata or {})},
        "payment_intent_data": {"metadata": {"transaction_uuid": reference}},
    }
    if customer_email:
        params["customer_email"] = customer_email
    return _request("POST", "/checkout/sessions", secret_key, params)


def retrieve_checkout_session(*, secret_key: str, session_id: str) -> dict:
    return _request("GET", f"/checkout/sessions/{quote(session_id, safe='')}", secret_key)


def verify_webhook(payload: bytes, signature_header: str, secret: str) -> dict:
    """Verify a Stripe-Signature header and return the parsed event."""
    if not secret:
        raise StripeError("Stripe webhook secret is not configured.")
    timestamp = None
    signatures: list[str] = []
    for part in (signature_header or "").split(","):
        key, _, value = part.strip().partition("=")
        if key == "t":
            timestamp = value
        elif key == "v1":
            signatures.append(value)
    if not timestamp or not signatures:
        raise StripeError("Malformed Stripe-Signature header.")
    try:
        if abs(time.time() - int(timestamp)) > WEBHOOK_TOLERANCE_SECONDS:
            raise StripeError("Stripe webhook timestamp outside tolerance.")
    except ValueError as exc:
        raise StripeError("Invalid Stripe webhook timestamp.") from exc

    signed_payload = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, sig) for sig in signatures):
        raise StripeError("Stripe webhook signature mismatch.")
    return json.loads(payload.decode("utf-8"))
