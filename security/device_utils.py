import re
from dataclasses import dataclass


@dataclass
class ClientDeviceInfo:
    device_id: str = ""
    device_name: str = ""
    model: str = ""
    platform: str = "unknown"
    os_version: str = ""
    app_version: str = ""
    push_token: str = ""
    location: str = ""


def get_client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def parse_user_agent(user_agent: str) -> tuple[str, str]:
    ua = user_agent or ""
    browser = "Unknown"
    os_name = "Unknown"

    if "Chrome/" in ua and "Edg/" not in ua:
        browser = "Chrome"
    elif "Edg/" in ua:
        browser = "Edge"
    elif "Firefox/" in ua:
        browser = "Firefox"
    elif "Safari/" in ua and "Chrome" not in ua:
        browser = "Safari"

    if "Android" in ua:
        os_name = "Android"
        match = re.search(r"Android (\d+(?:\.\d+)?)", ua)
        if match:
            os_name = f"Android {match.group(1)}"
    elif "iPhone" in ua or "iPad" in ua:
        os_name = "iOS"
        match = re.search(r"OS (\d+[_\d]*)", ua)
        if match:
            os_name = f"iOS {match.group(1).replace('_', '.')}"
    elif "Windows" in ua:
        os_name = "Windows"
    elif "Mac OS X" in ua or "Macintosh" in ua:
        os_name = "macOS"
    elif "Linux" in ua:
        os_name = "Linux"

    return browser, os_name


def extract_device_info(request) -> ClientDeviceInfo:
    data = getattr(request, "data", None) or {}
    if hasattr(data, "get"):
        payload = data
    else:
        payload = {}

    device_id = (payload.get("device_id") or request.headers.get("X-Device-Id") or "").strip()
    return ClientDeviceInfo(
        device_id=device_id,
        device_name=(payload.get("device_name") or "").strip(),
        model=(payload.get("model") or "").strip(),
        platform=(payload.get("platform") or request.headers.get("X-Platform") or "unknown").strip().lower(),
        os_version=(payload.get("os_version") or "").strip(),
        app_version=(payload.get("app_version") or request.headers.get("X-App-Version") or "").strip(),
        push_token=(payload.get("push_token") or "").strip(),
        location=(payload.get("location") or "").strip(),
    )
