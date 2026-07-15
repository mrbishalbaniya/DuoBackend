from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _tokenize_tags(tags: list[Any] | None) -> list[str]:
    out: list[str] = []
    for raw in tags or []:
        text = _norm(raw).lower()
        if not text:
            continue
        out.append(text)
    return out


def _parse_pref_values(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw or not isinstance(raw, str):
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def _split_name(full_name: str) -> tuple[str, str]:
    parts = [p for p in full_name.strip().split() if p]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


@dataclass
class ProfileContext:
    """Normalized snapshot of profile fields used by offline NLG engines."""

    user_id: int
    first_name: str = ""
    last_name: str = ""
    gender: str = ""
    age: int | None = None
    location: str = ""
    city: str = ""
    district: str = ""
    province: str = ""
    country: str = ""
    religion: str = ""
    caste: str = ""
    education: str = ""
    occupation: str = ""
    relationship_goal: str = ""
    marital_status: str = ""
    personality: str = ""
    lifestyle: str = ""
    smoking: str = ""
    drinking: str = ""
    exercise: str = ""
    interests: list[str] = field(default_factory=list)
    hobbies: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    pref_age_min: int | None = None
    pref_age_max: int | None = None
    pref_gender: str = ""
    pref_location: str = ""
    pref_religion: str = ""
    pref_relationship_goal: str = ""
    existing_bio: str = ""
    looking_for_text: str = ""
    future_goals_text: str = ""
    height: str = ""
    income: str = ""

    @classmethod
    def from_profile(cls, profile) -> "ProfileContext":
        prefs = _parse_pref_values(getattr(profile, "pref_values", ""))
        tags = _tokenize_tags(getattr(profile, "lifestyle_tags", None))

        interests: list[str] = []
        smoking = drinking = exercise = personality = lifestyle = marital = ""
        for tag in tags:
            if tag.startswith("smoking:"):
                smoking = tag.split(":", 1)[1]
            elif tag.startswith("drinking:"):
                drinking = tag.split(":", 1)[1]
            elif tag.startswith("exercise:"):
                exercise = tag.split(":", 1)[1]
            elif tag.startswith("marital:"):
                marital = tag.split(":", 1)[1]
            elif tag in {"introvert", "extrovert", "ambivert"}:
                personality = tag
            elif tag in {"homebody", "balanced", "outgoing", "adventurous"}:
                lifestyle = tag
            else:
                interests.append(tag)

        location = _norm(getattr(profile, "location", ""))
        city = _norm(prefs.get("municipality") or prefs.get("city") or "")
        district = _norm(prefs.get("district") or "")
        province = _norm(prefs.get("province") or "")
        country = _norm(prefs.get("country") or "")
        if not city and location:
            city = location.split(",")[0].strip()

        first, last = _split_name(_norm(getattr(profile, "full_name", "")))
        gender_map = {"M": "male", "F": "female", "O": "other"}
        gender = gender_map.get(_norm(getattr(profile, "gender", "")), _norm(getattr(profile, "gender", "")).lower())

        return cls(
            user_id=int(profile.user_id),
            first_name=first,
            last_name=last,
            gender=gender,
            age=getattr(profile, "age", None),
            location=location,
            city=city,
            district=district,
            province=province,
            country=country or ("Nepal" if "nepal" in location.lower() else ""),
            religion=_norm(getattr(profile, "religion", "")),
            caste=_norm(prefs.get("caste") or ""),
            education=_norm(getattr(profile, "education", "")),
            occupation=_norm(getattr(profile, "occupation", "")),
            relationship_goal=_norm(getattr(profile, "relationship_goal", "")),
            marital_status=marital or _norm(prefs.get("maritalStatus") or ""),
            personality=personality or _norm(prefs.get("personality") or ""),
            lifestyle=lifestyle or _norm(prefs.get("lifestyle") or ""),
            smoking=smoking,
            drinking=drinking,
            exercise=exercise,
            interests=interests,
            hobbies=[_norm(x).lower() for x in (prefs.get("hobbies") or []) if _norm(x)],
            languages=[_norm(x).lower() for x in (prefs.get("languages") or []) if _norm(x)],
            pref_age_min=getattr(profile, "pref_age_min", None),
            pref_age_max=getattr(profile, "pref_age_max", None),
            pref_gender=_norm(getattr(profile, "pref_gender", "")),
            pref_location=_norm(getattr(profile, "pref_location", "")),
            pref_religion=_norm(prefs.get("preferredReligion") or ""),
            pref_relationship_goal=_norm(getattr(profile, "pref_relationship_goal", "")),
            existing_bio=_norm(getattr(profile, "bio", "")),
            looking_for_text=_norm(prefs.get("lookingForText") or ""),
            future_goals_text=_norm(prefs.get("futureGoals") or ""),
            height=_norm(prefs.get("height") or getattr(profile, "pref_min_height", "") or ""),
            income=_norm(prefs.get("monthlyIncome") or ""),
        )

    def fingerprint_payload(self) -> dict[str, Any]:
        return {
            "education": self.education.lower(),
            "occupation": self.occupation.lower(),
            "location": self.location.lower(),
            "religion": self.religion.lower(),
            "relationship_goal": self.relationship_goal.lower(),
            "lifestyle": sorted(
                [
                    f"smoking:{self.smoking}",
                    f"drinking:{self.drinking}",
                    f"exercise:{self.exercise}",
                    f"personality:{self.personality}",
                    f"lifestyle:{self.lifestyle}",
                    *sorted(self.interests),
                ]
            ),
            "prefs": {
                "age_min": self.pref_age_min,
                "age_max": self.pref_age_max,
                "gender": self.pref_gender.lower(),
                "religion": self.pref_religion.lower(),
                "goal": self.pref_relationship_goal.lower(),
            },
        }

    def fingerprint(self) -> str:
        payload = json.dumps(self.fingerprint_payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def interest_keys(self) -> list[str]:
        keys: list[str] = []
        for item in [*self.interests, *self.hobbies]:
            cleaned = re.sub(r"[^a-z0-9\s\+\#\.\-]", "", item.lower()).strip()
            if cleaned:
                keys.append(cleaned.replace(" ", "_"))
                # also keep bare token for matching gym, travel, etc.
                for token in cleaned.split():
                    if len(token) > 2:
                        keys.append(token)
        # unique preserve order
        seen: set[str] = set()
        out: list[str] = []
        for key in keys:
            if key in seen:
                continue
            seen.add(key)
            out.append(key)
        return out
