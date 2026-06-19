import math
from typing import Tuple

CITY_COORDS = {
    "kathmandu": (27.7172, 85.324),
    "pokhara": (28.2096, 83.9856),
    "lalitpur": (27.6588, 85.3247),
    "bhaktapur": (27.671, 85.4298),
    "chitwan": (27.5291, 84.3542),
    "biratnagar": (26.4525, 87.2718),
    "dharan": (26.8147, 87.2848),
    "butwal": (27.7, 83.4483),
}

DEFAULT_CENTER = (27.7172, 85.324)


def _hash_seed(value: str) -> int:
    h = 0
    for ch in value:
        h = ((h << 5) - h + ord(ch)) & 0xFFFFFFFF
    return abs(h)


def find_city_center(location: str) -> Tuple[float, float]:
    normalized = (location or "").lower()
    for city, coords in CITY_COORDS.items():
        if city in normalized:
            return coords
    return DEFAULT_CENTER


def profile_coordinates(location: str | None, user_id: int | str | None) -> Tuple[float, float]:
    base = find_city_center((location or "").strip() or "Kathmandu, Nepal")
    seed = _hash_seed(str(user_id if user_id is not None else location or "0"))
    angle = (seed % 360) * (math.pi / 180)
    radius = 0.008 + (seed % 100) / 10000
    return (
        base[0] + math.cos(angle) * radius,
        base[1] + math.sin(angle) * radius,
    )


def haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    lat1, lon1 = a
    lat2, lon2 = b
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    x = (
        math.sin(d_lat / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(d_lon / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(x))
