import base64
import hashlib
import hmac
import json
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings


def _format_amount(value: Decimal | str | float) -> str:
    """Format NPR amounts for eSewa form fields and signatures.

    Whole-number amounts use integer strings (e.g. 499) to match eSewa UAT examples.
    """
    amount = Decimal(str(value)).quantize(Decimal("0.01"))
    if amount == amount.to_integral_value():
        return str(int(amount))
    return f"{amount:.2f}"


def _stringify_signed_value(field_name: str, value: Any) -> str:
    if value is None:
        return ""
    if field_name == "total_amount":
        # eSewa response signatures use float strings (e.g. 1000.0).
        return str(float(value))
    return str(value)


def generate_signature(message: str, secret_key: str) -> str:
    digest = hmac.new(
        secret_key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


def generate_payment_signature(
    total_amount: Decimal | str | float,
    transaction_uuid: str,
    product_code: str,
    secret_key: str,
) -> str:
    message = (
        f"total_amount={_format_amount(total_amount)},"
        f"transaction_uuid={transaction_uuid},"
        f"product_code={product_code}"
    )
    return generate_signature(message, secret_key)


def verify_response_signature(payload: dict[str, Any], secret_key: str) -> bool:
    signed_field_names = payload.get("signed_field_names")
    if not signed_field_names:
        return False

    parts = []
    for field_name in str(signed_field_names).split(","):
        field_name = field_name.strip()
        if not field_name or field_name == "signature":
            continue
        parts.append(f"{field_name}={_stringify_signed_value(field_name, payload.get(field_name))}")

    expected = generate_signature(",".join(parts), secret_key)
    received = str(payload.get("signature", ""))
    return hmac.compare_digest(expected, received)


def decode_callback_payload(encoded_data: str) -> dict[str, Any]:
    decoded = base64.b64decode(encoded_data).decode("utf-8")
    return json.loads(decoded)


def check_transaction_status(
    product_code: str,
    total_amount: Decimal | str | float,
    transaction_uuid: str,
) -> dict[str, Any]:
    query = urlencode(
        {
            "product_code": product_code,
            "total_amount": _format_amount(total_amount),
            "transaction_uuid": transaction_uuid,
        }
    )
    url = f"{settings.ESEWA_STATUS_URL.rstrip('/')}/?{query}"
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))
