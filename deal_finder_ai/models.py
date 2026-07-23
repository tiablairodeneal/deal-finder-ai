from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Listing:
    title: str
    source: str
    listing_url: str | None = None
    industry: str | None = None
    location: str | None = None
    asking_price: int | None = None
    annual_revenue: int | None = None
    cash_flow: int | None = None
    financing: str | None = None
    seller_financing_offered: bool = False
    description: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScoreResult:
    score: int
    explanation: str
    matched_criteria: list[str]
    missed_criteria: list[str]
    status: str


@dataclass(frozen=True)
class IndustryAssessment:
    subindustry: str
    grade: str
    assessment: str
    cache_key: str
    internal_score: int


@dataclass(frozen=True)
class EnrichedListing:
    listing: Listing
    duplicate_key: str
    score: ScoreResult
    executive_summary: str
    industry_assessment: IndustryAssessment | None = None
