"""Keep place names in English (Latin script).

OpenStreetMap returns local-script names (e.g. "काठमाडौँ महानगरपालिका, नेपाल")
unless asked for English. Clients now request English, but this guards the
server: any Devanagari place text is converted before it is stored.
"""

from __future__ import annotations

import logging
import re

import requests

logger = logging.getLogger(__name__)

DEVANAGARI = re.compile("[ऀ-ॿ]")

# Common admin words / places, used before (and if) the network lookup fails.
_KNOWN = {
    "नेपाल": "Nepal",
    "काठमाडौँ": "Kathmandu",
    "काठमाडौं": "Kathmandu",
    "ललितपुर": "Lalitpur",
    "भक्तपुर": "Bhaktapur",
    "पोखरा": "Pokhara",
    "चितवन": "Chitwan",
    "भरतपुर": "Bharatpur",
    "विराटनगर": "Biratnagar",
    "बिराटनगर": "Biratnagar",
    "धरान": "Dharan",
    "बुटवल": "Butwal",
    "जनकपुर": "Janakpur",
    "हेटौंडा": "Hetauda",
    "धनगढी": "Dhangadhi",
    "नेपालगञ्ज": "Nepalgunj",
    "बागमती प्रदेश": "Bagmati",
    "गण्डकी प्रदेश": "Gandaki",
    "कोशी प्रदेश": "Koshi",
    "मधेश प्रदेश": "Madhesh",
    "लुम्बिनी प्रदेश": "Lumbini",
    "कर्णाली प्रदेश": "Karnali",
    "सुदूरपश्चिम प्रदेश": "Sudurpashchim",
    "नया बानेश्वर": "New Baneshwor",
    "बानेश्वर": "Baneshwor",
}
# Administrative suffixes dropped from city names ("Kathmandu Metropolitan City" -> "Kathmandu").
_SUFFIXES = ("उप-महानगरपालिका", "उपमहानगरपालिका", "महानगरपालिका", "गाउँपालिका", "नगरपालिका", "जिल्ला")
_EN_SUFFIXES = (
    " Sub-Metropolitan City",
    " Metropolitan City",
    " Rural Municipality",
    " Municipality",
    " District",
)

_NOMINATIM = "https://nominatim.openstreetmap.org"
_HEADERS = {"User-Agent": "DuoBackend/1.0", "Accept-Language": "en"}


def has_devanagari(text: str | None) -> bool:
    return bool(text and DEVANAGARI.search(text))


def short_english(name: str) -> str:
    name = name.strip()
    for suffix in _EN_SUFFIXES:
        if name.lower().endswith(suffix.lower()):
            return name[: -len(suffix)].strip()
    return name


def _from_table(part: str) -> str | None:
    text = part.strip()
    for suffix in _SUFFIXES:
        text = text.replace(suffix, "").strip()
    return _KNOWN.get(text) or _KNOWN.get(part.strip())


def _search_english(part: str) -> str | None:
    try:
        response = requests.get(
            f"{_NOMINATIM}/search",
            params={"q": part, "format": "json", "limit": 1, "accept-language": "en", "addressdetails": 1},
            headers=_HEADERS,
            timeout=6,
        )
        response.raise_for_status()
        results = response.json()
    except Exception:  # noqa: BLE001 - best effort, never block a save
        logger.debug("english_places: search failed for %r", part, exc_info=True)
        return None
    if not results:
        return None
    first = results[0]
    address = first.get("address") or {}
    for key in ("city", "town", "village", "municipality", "suburb", "neighbourhood", "county", "state", "country"):
        value = address.get(key)
        if value and not has_devanagari(value):
            return short_english(value)
    name = (first.get("name") or "").strip()
    return short_english(name) if name and not has_devanagari(name) else None


def to_english(text: str | None, *, network: bool = True) -> str:
    """Comma-separated place text with every Devanagari part made English.

    Unknown parts are looked up on OpenStreetMap (when [network]); anything
    still untranslatable is dropped rather than stored in Devanagari.
    """
    if not has_devanagari(text):
        return text or ""
    out: list[str] = []
    for part in (text or "").split(","):
        part = part.strip()
        if not part:
            continue
        if not has_devanagari(part):
            english = part
        else:
            english = _from_table(part) or (_search_english(part) if network else None)
        if english and english not in out:
            out.append(english)
    return ", ".join(out)


def reverse_english(lat: float, lon: float) -> str | None:
    """Short English "Street, Area, City" for coordinates; None on failure."""
    try:
        response = requests.get(
            f"{_NOMINATIM}/reverse",
            params={"lat": lat, "lon": lon, "format": "json", "zoom": 18, "addressdetails": 1, "accept-language": "en"},
            headers=_HEADERS,
            timeout=6,
        )
        response.raise_for_status()
        address = response.json().get("address") or {}
    except Exception:  # noqa: BLE001
        return None

    def pick(keys):
        for key in keys:
            value = (address.get(key) or "").strip()
            if value:
                return value
        return ""

    parts: list[str] = []
    for value in (
        pick(["road", "pedestrian", "footway"]),
        pick(["neighbourhood", "suburb", "quarter"]),
        short_english(pick(["city", "town", "village", "municipality", "county"])),
    ):
        if value and value not in parts and not has_devanagari(value):
            parts.append(value)
    return ", ".join(parts) or None
