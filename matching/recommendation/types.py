from __future__ import annotations

from dataclasses import dataclass, field

from accounts.models import Profile


@dataclass(frozen=True)
class SearchConfig:
  """Hard-filter configuration for a discovery search stage."""

  age_min: int
  age_max: int
  max_distance_km: int
  location_pref: str = ""
  apply_location: bool = True
  gender: str = "everyone"
  relationship_goal: str | None = "everyone"
  verified_only: bool = False
  prefer_verified: bool = False
  prefer_active: bool = False
  prefer_popular: bool = False
  prefer_new: bool = False
  ignore_distance: bool = False
  recycled_skips: bool = False


@dataclass
class ScoredProfile:
  profile: Profile
  score: float
  distance_km: float


@dataclass
class DiscoverResult:
  profiles: list[Profile]
  expanded_search: bool = False
  relaxation_stage: str = "strict"
  recycled_skips: bool = False
  meta: dict = field(default_factory=dict)
