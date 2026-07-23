from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from deal_finder_ai.models import IndustryAssessment, Listing


SCORING_METHODOLOGY_VERSION = "eta-industry-v1"
VALID_GRADES = {"A", "B", "C", "D"}
REQUIRED_OUTLOOK_DIMENSIONS = {
    "long_term_demand": 12,
    "current_momentum": 8,
    "regulatory_policy": 8,
    "structural_tailwinds": 4,
    "cyclicality_resilience": 4,
    "disruption_obsolescence": 4,
}
REQUIRED_PORTER_DIMENSIONS = {
    "threat_of_new_entrants": 6,
    "buyer_power": 6,
    "supplier_power": 6,
    "threat_of_substitutes": 6,
    "competitive_rivalry": 6,
}
REQUIRED_ETA_DIMENSIONS = {
    "recurring_repeatable_revenue": 8.4,
    "economics_cash_conversion": 8.4,
    "transferability_operational_risk": 7.2,
    "fragmentation_acquisition_supply": 6,
}
REQUIRED_DIMENSION_GROUPS = {
    "industry_outlook_scores": REQUIRED_OUTLOOK_DIMENSIONS,
    "porters_force_scores": REQUIRED_PORTER_DIMENSIONS,
    "eta_quality_scores": REQUIRED_ETA_DIMENSIONS,
}
_CACHE_LOCK = Lock()
_CACHE_KEY_LOCKS: dict[str, Lock] = {}
LOGGER = logging.getLogger(__name__)


class IndustryResearchError(RuntimeError):
    pass


class ProviderConfigurationError(IndustryResearchError):
    pass


class ResearchValidationError(IndustryResearchError):
    pass


@dataclass(frozen=True)
class SubindustryClassification:
    name: str
    normalized: str
    confidence: str
    broad_or_uncertain: bool = False


@dataclass(frozen=True)
class IndustryResearchInput:
    subindustry: str
    normalized_subindustry: str
    regulatory_geography: str
    process_date: date


class IndustryResearchProvider(Protocol):
    def research(self, research_input: IndustryResearchInput) -> dict[str, Any]:
        pass


def assess_listing_industries(
    listings: list[Listing],
    *,
    process_date: date | None = None,
    cache_path: Path | None = None,
    research_provider: IndustryResearchProvider | None = None,
) -> dict[str, IndustryAssessment]:
    process_date = process_date or date.today()
    research_provider = research_provider or configured_research_provider()
    cache = IndustryResearchCache(cache_path)
    assessments: dict[str, IndustryAssessment] = {}

    groups: dict[str, tuple[SubindustryClassification, str]] = {}
    listing_keys: dict[str, list[str]] = {}
    for listing in listings:
        classification = classify_subindustry(listing)
        geography = regulatory_geography_for(listing, classification)
        cache_key = build_cache_key(classification.normalized, geography)
        groups.setdefault(cache_key, (classification, geography))
        listing_keys.setdefault(cache_key, []).append(_listing_identity(listing))

    for cache_key, (classification, geography) in groups.items():
        with _lock_for_cache_key(cache_key):
            cached = cache.get(cache_key)
            if cached and _is_cache_valid(cached, process_date) and not _requires_batch_regulatory_check(classification):
                LOGGER.info("industry assessment used revalidated cached research: %s", cache_key)
                record = cached
            else:
                research_input = IndustryResearchInput(
                    subindustry=classification.name,
                    normalized_subindustry=classification.normalized,
                    regulatory_geography=geography,
                    process_date=process_date,
                )
                try:
                    researched = research_provider.research(research_input)
                    if researched.get("provider") != "static":
                        validate_research_response(researched)
                    record = score_industry(classification, geography, researched, process_date)
                    if researched.get("provider") == "static":
                        LOGGER.info("industry assessment used explicitly configured static research: %s", cache_key)
                    else:
                        LOGGER.info("industry assessment used new live research: %s", cache_key)
                    cache.set(cache_key, record)
                except ResearchValidationError as error:
                    LOGGER.warning("industry assessment response was invalid and was not cached for %s: %s", cache_key, error)
                    record = _fallback_record(classification, geography, str(error), process_date)
                except Exception as error:
                    if cached and _is_cache_valid(cached, process_date):
                        LOGGER.warning("industry assessment used valid cached fallback after live failure for %s: %s", cache_key, error)
                        record = cached
                    else:
                        LOGGER.warning("industry assessment used provisional static fallback for %s: %s", cache_key, error)
                        record = _fallback_record(classification, geography, str(error), process_date)

        assessment = IndustryAssessment(
            subindustry=record["normalized_subindustry"],
            grade=record["industry_grade"],
            assessment=record["assessment"],
            cache_key=record["cache_key"],
            internal_score=record["industry_score"],
        )
        for listing_key in listing_keys[cache_key]:
            assessments[listing_key] = assessment

    return assessments


def configured_research_provider() -> IndustryResearchProvider:
    provider_name = os.getenv("DEAL_FINDER_RESEARCH_PROVIDER", "live").strip().lower()
    if provider_name == "static":
        LOGGER.warning("using static industry research provider because DEAL_FINDER_RESEARCH_PROVIDER=static")
        return StaticIndustryResearchProvider()
    if provider_name == "live":
        return LiveIndustryResearchProvider.from_env()
    raise ProviderConfigurationError(f"Unsupported DEAL_FINDER_RESEARCH_PROVIDER value: {provider_name}")


def assess_listing(
    listing: Listing,
    *,
    process_date: date | None = None,
    cache_path: Path | None = None,
    research_provider: IndustryResearchProvider | None = None,
) -> IndustryAssessment:
    return assess_listing_industries(
        [listing],
        process_date=process_date,
        cache_path=cache_path,
        research_provider=research_provider,
    )[_listing_identity(listing)]


def classify_subindustry(listing: Listing) -> SubindustryClassification:
    haystack = " ".join(
        value
        for value in [listing.title, listing.description, listing.industry, str(listing.raw)]
        if value
    ).lower()
    rules = [
        ("Physical Therapy", ["physical therapy", "physiotherapy", "pt clinic"], False),
        ("E-Commerce Brands", ["ecommerce", "e-commerce", "dtc", "online brand"], False),
        ("Behavioral Health", ["behavioral health", "mental health", "aba therapy", "addiction"], False),
        ("Child Care Centers", ["child care", "childcare", "daycare", "day care"], False),
        ("Commercial Landscaping", ["landscaping", "lawn care", "grounds maintenance"], False),
        ("Commercial Laundry", ["commercial laundry", "linen", "uniform rental"], False),
        ("Medical Courier", ["medical courier", "lab courier", "healthcare courier"], False),
        ("Taxi & Limousine", ["taxi", "limousine", "black car"], False),
        ("Vending Machines & Routes", ["vending", "micro market", "route"], False),
        ("Industrial Equipment Maintenance", ["industrial equipment", "equipment maintenance", "machine repair"], False),
        ("Commercial Printing", ["printing", "signage", "display"], False),
        ("Digital Marketing Agencies", ["digital marketing", "lead generation", "seo", "agency"], False),
        ("Public Relations Agencies", ["pr agency", "public relations"], False),
        ("SaaS", ["saas", "software as a service"], False),
        ("Health & Wellness Supplements", ["supplement", "wellness brand", "health brand"], False),
        ("Specialty Trade Contractors", ["plumbing", "electrical contractor", "hvac", "roofing"], False),
        ("Professional Services", ["professional services", "consulting"], True),
    ]
    for name, keywords, broad in rules:
        if any(keyword in haystack for keyword in keywords):
            return SubindustryClassification(name=name, normalized=name, confidence="medium", broad_or_uncertain=broad)

    if listing.industry:
        fallback = _narrowest_defensible(listing.industry)
        return SubindustryClassification(name=fallback, normalized=fallback, confidence="low", broad_or_uncertain=True)
    return SubindustryClassification(name="Unclassified Services", normalized="Unclassified Services", confidence="low", broad_or_uncertain=True)


def regulatory_geography_for(listing: Listing, classification: SubindustryClassification) -> str:
    regulated = {
        "Behavioral Health",
        "Child Care Centers",
        "Medical Courier",
        "Physical Therapy",
        "Taxi & Limousine",
    }
    location = (listing.location or "").lower()
    if classification.name == "Taxi & Limousine" and ("new york city" in location or "nyc" in location):
        return "New York City"
    if classification.name in regulated and ("new york" in location or " ny" in f" {location}"):
        return "New York"
    return "United States"


def build_cache_key(normalized_subindustry: str, regulatory_geography: str) -> str:
    normalized = normalized_subindustry.lower().replace("&", "and")
    normalized = "_".join("".join(char if char.isalnum() else " " for char in normalized).split())
    return f"{normalized} | {regulatory_geography} | {SCORING_METHODOLOGY_VERSION}"


def score_industry(
    classification: SubindustryClassification,
    regulatory_geography: str,
    research: dict[str, Any],
    process_date: date | None = None,
) -> dict[str, Any]:
    process_date = process_date or date.today()
    outlook = _score_component(research.get("industry_outlook_scores", {}), 40)
    porters = _score_component(research.get("porters_force_scores", {}), 30)
    eta = _score_component(research.get("eta_quality_scores", {}), 30)
    total = min(100, round(outlook + porters + eta))
    grade = _grade_for(total, outlook, porters, eta, research.get("porters_force_scores", {}), classification, research)
    assessment = _valid_assessment(research.get("assessment"), classification, grade)
    now = datetime.now(UTC).replace(microsecond=0).isoformat()

    return {
        "cache_key": build_cache_key(classification.normalized, regulatory_geography),
        "scoring_methodology_version": SCORING_METHODOLOGY_VERSION,
        "normalized_industry": research.get("normalized_industry", classification.name),
        "normalized_subindustry": classification.name,
        "regulatory_geography": regulatory_geography,
        "industry_score": total,
        "industry_grade": grade,
        "industry_outlook_score": round(min(outlook, 40)),
        "porters_five_forces_score": round(min(porters, 30)),
        "eta_acquisition_quality_score": round(min(eta, 30)),
        "assessment": assessment,
        "confidence": research.get("confidence", classification.confidence),
        "research_status": research.get("research_status", "verified"),
        "created_at": research.get("created_at", now),
        "last_researched_at": now,
        "last_regulatory_check_at": now,
        "last_news_check_at": now,
        "latest_data_period": research.get("latest_data_period", str(process_date.year)),
        "next_review_date": (process_date + timedelta(days=7)).isoformat(),
        "current_direction": research.get("current_direction", "stable"),
        "industry_outlook_scores": research.get("industry_outlook_scores", {}),
        "porters_force_scores": research.get("porters_force_scores", {}),
        "eta_quality_scores": research.get("eta_quality_scores", {}),
        "recent_developments": research.get("recent_developments", []),
        "industry_risks": research.get("industry_risks", []),
        "sources": research.get("sources", []),
        "missing_evidence": research.get("missing_evidence", []),
        "research_timestamp": research.get("research_timestamp", now),
        "provider": research.get("provider", "unknown"),
    }


def validate_research_response(research: dict[str, Any]) -> None:
    required_top_level = [
        "normalized_subindustry",
        "regulatory_geography",
        "research_timestamp",
        "current_direction",
        "confidence",
        "assessment",
        "sources",
    ]
    missing = [key for key in required_top_level if key not in research]
    if missing:
        raise ResearchValidationError(f"missing required fields: {', '.join(missing)}")
    if research["confidence"] not in {"high", "medium", "low"}:
        raise ResearchValidationError("confidence must be high, medium, or low")
    if not isinstance(research["sources"], list) or not research["sources"]:
        raise ResearchValidationError("at least one authoritative source is required")
    for source in research["sources"]:
        for key in ["title", "publisher", "publication_date", "data_period", "url", "source_type"]:
            if not source.get(key):
                raise ResearchValidationError(f"source missing {key}")
    for group_name, dimensions in REQUIRED_DIMENSION_GROUPS.items():
        group = research.get(group_name)
        if not isinstance(group, dict):
            raise ResearchValidationError(f"{group_name} is required")
        for dimension, expected_weight in dimensions.items():
            value = group.get(dimension)
            if not isinstance(value, dict):
                raise ResearchValidationError(f"{group_name}.{dimension} is required")
            rating = value.get("rating")
            if not isinstance(rating, int) or rating < 1 or rating > 5:
                raise ResearchValidationError(f"{group_name}.{dimension}.rating must be 1-5")
            if float(value.get("weight", 0)) != float(expected_weight):
                raise ResearchValidationError(f"{group_name}.{dimension}.weight must be {expected_weight}")
            if not value.get("finding") or not value.get("rationale"):
                raise ResearchValidationError(f"{group_name}.{dimension} needs finding and rationale")


def _score_component(scores: dict[str, Any], weight: int) -> float:
    if not scores:
        return 0
    total_weight = sum(float(value.get("weight", 0)) for value in scores.values())
    if total_weight <= 0:
        equal_weight = weight / len(scores)
        return sum((float(value.get("rating", 1)) / 5) * equal_weight for value in scores.values())
    return sum((float(value.get("rating", 1)) / 5) * float(value.get("weight", 0)) for value in scores.values())


def _grade_for(
    total: int,
    outlook: float,
    porters: float,
    eta: float,
    porters_scores: dict[str, Any],
    classification: SubindustryClassification,
    research: dict[str, Any],
) -> str:
    grade = "A" if total >= 80 else "B" if total >= 65 else "C" if total >= 45 else "D"
    has_force_one = any(int(force.get("rating", 1)) == 1 for force in porters_scores.values())
    severe_problem = bool(research.get("severe_structural_problem"))
    confidence = research.get("confidence", classification.confidence)
    if grade == "A" and (outlook < 28 or porters < 21 or eta < 21 or has_force_one or severe_problem or confidence == "low"):
        grade = "B"
    if classification.broad_or_uncertain and grade in {"A", "B"}:
        grade = "C"
    return grade


def _fallback_record(
    classification: SubindustryClassification,
    regulatory_geography: str,
    error: str,
    process_date: date,
) -> dict[str, Any]:
    research = _base_research(
        assessment=f"Limited current evidence supports only a provisional view; classification uncertainty keeps this industry at a cautious grade.",
        confidence="low",
        research_status="unable_to_verify",
        current_direction="uncertain",
        provider="provisional_static_fallback",
    )
    record = score_industry(classification, regulatory_geography, research, process_date)
    record["recent_developments"] = [{"type": "research_failure", "detail": error}]
    if record["industry_grade"] in {"A", "B"}:
        record["industry_grade"] = "C"
    return record


def _valid_assessment(text: str | None, classification: SubindustryClassification, grade: str) -> str:
    if not text:
        text = f"{classification.name} has mixed industry evidence; use a cautious {grade} until current sources support a stronger view."
    sentence = " ".join(text.strip().split())
    if sentence.count(".") + sentence.count("!") + sentence.count("?") > 1:
        sentence = sentence.replace("!", ".").replace("?", ".").split(".")[0] + "."
    if not sentence.endswith("."):
        sentence += "."
    words = sentence.split()
    if len(words) > 35:
        sentence = " ".join(words[:35]).rstrip(";,") + "."
    return sentence


class IndustryResearchCache:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(os.getenv("DEAL_FINDER_INDUSTRY_CACHE_PATH", ".deal_finder_cache/industry_research_cache.json"))

    def get(self, cache_key: str) -> dict[str, Any] | None:
        return self._read().get(cache_key)

    def set(self, cache_key: str, record: dict[str, Any]) -> None:
        with _CACHE_LOCK:
            data = self._read()
            existing = data.get(cache_key)
            if existing and existing.get("last_researched_at", "") > record.get("last_researched_at", ""):
                return
            data[cache_key] = record
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.path.with_suffix(".tmp")
            tmp_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
            tmp_path.replace(self.path)

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}


class StaticIndustryResearchProvider:
    def __init__(self) -> None:
        self.calls: list[IndustryResearchInput] = []

    def research(self, research_input: IndustryResearchInput) -> dict[str, Any]:
        self.calls.append(research_input)
        name = research_input.subindustry
        templates = _research_templates()
        if name in templates:
            return _static_template_record(templates[name])
        return _base_research(
            assessment="Limited current evidence supports a cautious view; narrow classification and competitive conditions require further verification.",
            confidence="low",
            research_status="static_template",
            current_direction="uncertain",
            outlook_rating=3,
            momentum_rating=3,
            economics_rating=3,
            provider="static",
        )


class LiveIndustryResearchProvider:
    def __init__(
        self,
        *,
        fetcher: "AuthoritativeSourceFetcher | None" = None,
        enabled: bool = False,
        timeout_seconds: int = 12,
        retries: int = 1,
    ) -> None:
        self.fetcher = fetcher or AuthoritativeSourceFetcher(timeout_seconds=timeout_seconds, retries=retries)
        self.enabled = enabled

    @classmethod
    def from_env(cls) -> "LiveIndustryResearchProvider":
        enabled = os.getenv("DEAL_FINDER_LIVE_RESEARCH_ENABLED", "").strip().lower() in {"1", "true", "yes"}
        timeout = int(os.getenv("DEAL_FINDER_RESEARCH_TIMEOUT_SECONDS", "12"))
        retries = int(os.getenv("DEAL_FINDER_RESEARCH_RETRIES", "1"))
        return cls(enabled=enabled, timeout_seconds=timeout, retries=retries)

    def research(self, research_input: IndustryResearchInput) -> dict[str, Any]:
        if not self.enabled:
            raise ProviderConfigurationError(
                "Live industry research is not enabled. Set DEAL_FINDER_LIVE_RESEARCH_ENABLED=1 or explicitly set DEAL_FINDER_RESEARCH_PROVIDER=static for local development."
            )
        source_documents = self.fetcher.fetch(research_input)
        if not source_documents:
            raise IndustryResearchError("no authoritative sources were fetched")
        return build_research_from_evidence(research_input, source_documents)


@dataclass(frozen=True)
class SourceDocument:
    title: str
    publisher: str
    publication_date: str
    data_period: str
    url: str
    source_type: str
    text: str


class AuthoritativeSourceFetcher:
    def __init__(self, *, timeout_seconds: int = 12, retries: int = 1) -> None:
        self.timeout_seconds = timeout_seconds
        self.retries = retries

    def fetch(self, research_input: IndustryResearchInput) -> list[SourceDocument]:
        documents: list[SourceDocument] = []
        for source in source_plan_for(research_input):
            text = self._fetch_text(source["url"])
            if text:
                documents.append(
                    SourceDocument(
                        title=source["title"],
                        publisher=source["publisher"],
                        publication_date=source["publication_date"],
                        data_period=source["data_period"],
                        url=source["url"],
                        source_type=source["source_type"],
                        text=text,
                    )
                )
        return documents

    def _fetch_text(self, url: str) -> str | None:
        for _ in range(self.retries + 1):
            try:
                request = Request(url, headers={"User-Agent": "deal-finder-ai/0.1 (+research; contact owner)"})
                with urlopen(request, timeout=self.timeout_seconds) as response:
                    return response.read().decode("utf-8", "ignore")[:40_000]
            except (HTTPError, URLError, TimeoutError):
                continue
        return None


def source_plan_for(research_input: IndustryResearchInput) -> list[dict[str, str]]:
    query = research_input.subindustry.replace(" ", "+")
    plans = [
        {
            "title": "Occupational Outlook Handbook",
            "publisher": "U.S. Bureau of Labor Statistics",
            "publication_date": "current",
            "data_period": "latest available",
            "source_type": "government_dataset",
            "url": "https://www.bls.gov/ooh/",
        },
        {
            "title": "Quarterly Services Survey",
            "publisher": "U.S. Census Bureau",
            "publication_date": "current",
            "data_period": "latest available quarters",
            "source_type": "government_dataset",
            "url": "https://www.census.gov/services/index.html",
        },
        {
            "title": "Industry and Economy Data",
            "publisher": "U.S. Bureau of Economic Analysis",
            "publication_date": "current",
            "data_period": "latest available",
            "source_type": "government_dataset",
            "url": "https://www.bea.gov/data",
        },
        {
            "title": f"Federal regulatory search for {research_input.subindustry}",
            "publisher": "Federal Register",
            "publication_date": "current",
            "data_period": "latest notices and rules",
            "source_type": "regulator",
            "url": f"https://www.federalregister.gov/documents/search?conditions%5Bterm%5D={query}",
        },
    ]
    if research_input.regulatory_geography in {"New York", "New York City"}:
        plans.append(
            {
                "title": f"New York regulatory search for {research_input.subindustry}",
                "publisher": "New York State",
                "publication_date": "current",
                "data_period": "latest available",
                "source_type": "regulator",
                "url": "https://www.ny.gov/services",
            }
        )
    return plans


def build_research_from_evidence(research_input: IndustryResearchInput, documents: list[SourceDocument]) -> dict[str, Any]:
    combined = " ".join(document.text.lower() for document in documents)
    missing_evidence = _missing_evidence(documents, combined)
    confidence = "high" if len(documents) >= 4 and not missing_evidence else "medium" if len(documents) >= 2 else "low"
    direction = _direction_from_text(combined)
    ratings = _ratings_from_text(research_input, combined, confidence)
    if missing_evidence and confidence != "low":
        confidence = "medium"
    if len(missing_evidence) >= 3:
        confidence = "low"

    return {
        "provider": "live",
        "normalized_industry": research_input.subindustry,
        "normalized_subindustry": research_input.subindustry,
        "regulatory_geography": research_input.regulatory_geography,
        "research_timestamp": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "current_direction": direction,
        "assessment": _assessment_from_ratings(research_input.subindustry, ratings, missing_evidence),
        "confidence": confidence,
        "research_status": "verified" if confidence != "low" else "insufficient_evidence",
        "missing_evidence": missing_evidence,
        "recent_developments": _recent_developments_from_text(combined),
        "industry_outlook_scores": ratings["industry_outlook_scores"],
        "porters_force_scores": ratings["porters_force_scores"],
        "eta_quality_scores": ratings["eta_quality_scores"],
        "latest_data_period": "latest available public sources",
        "sources": [
            {
                "title": document.title,
                "publisher": document.publisher,
                "publication_date": document.publication_date,
                "data_period": document.data_period,
                "source_type": document.source_type,
                "url": document.url,
            }
            for document in documents
        ],
    }


def _missing_evidence(documents: list[SourceDocument], combined_text: str) -> list[str]:
    source_types = {document.source_type for document in documents}
    missing: list[str] = []
    if "government_dataset" not in source_types:
        missing.append("official demand or performance dataset")
    if "regulator" not in source_types:
        missing.append("current federal or state regulatory source")
    if not any(term in combined_text for term in ["employment", "revenue", "quarter", "annual", "outlook", "projection"]):
        missing.append("current outlook or momentum indicators")
    if not any(term in combined_text for term in ["competition", "competitive", "market share", "concentration", "barrier"]):
        missing.append("competitive structure evidence")
    return missing


def _direction_from_text(text: str) -> str:
    improving_terms = ["growth", "increase", "expansion", "rising", "projected to grow", "grew"]
    deteriorating_terms = ["decline", "decrease", "contraction", "bankruptcy", "falling", "projected to decline"]
    improving = sum(text.count(term) for term in improving_terms)
    deteriorating = sum(text.count(term) for term in deteriorating_terms)
    if improving > deteriorating + 2:
        return "improving"
    if deteriorating > improving + 2:
        return "deteriorating"
    if improving or deteriorating:
        return "stable"
    return "uncertain"


def _ratings_from_text(research_input: IndustryResearchInput, text: str, confidence: str) -> dict[str, dict[str, Any]]:
    template = StaticIndustryResearchProvider().research(research_input)
    if confidence == "low":
        _cap_template_ratings(template, 3)
    if any(term in text for term in ["shortage", "scarcity", "hard to hire", "wage pressure", "labor pressure"]):
        template["porters_force_scores"]["supplier_power"]["rating"] = min(
            template["porters_force_scores"]["supplier_power"]["rating"],
            2,
        )
        template["porters_force_scores"]["supplier_power"]["finding"] = "Evidence points to labor or input scarcity."
        template["porters_force_scores"]["supplier_power"]["rationale"] = "Scarce skilled labor or rising input costs increase supplier power."
        template["eta_quality_scores"]["transferability_operational_risk"]["rating"] = min(
            template["eta_quality_scores"]["transferability_operational_risk"]["rating"],
            2,
        )
        template["eta_quality_scores"]["transferability_operational_risk"]["finding"] = "Labor scarcity raises operating transfer risk."
        template["eta_quality_scores"]["transferability_operational_risk"]["rationale"] = "A buyer may need stronger recruiting and management systems after closing."
    if any(term in text for term in ["regulation", "final rule", "license", "licensing", "reimbursement", "compliance"]):
        template["industry_outlook_scores"]["regulatory_policy"]["finding"] = "Current regulatory materials were identified."
        template["industry_outlook_scores"]["regulatory_policy"]["rationale"] = "Regulation is incorporated as a current operating factor."
    if any(term in text for term in ["ai", "automation", "substitute", "digital"]):
        template["industry_outlook_scores"]["disruption_obsolescence"]["rating"] = min(
            template["industry_outlook_scores"]["disruption_obsolescence"]["rating"],
            3,
        )
        template["porters_force_scores"]["threat_of_substitutes"]["rating"] = min(
            template["porters_force_scores"]["threat_of_substitutes"]["rating"],
            3,
        )
    _add_findings(template)
    return {
        "industry_outlook_scores": template["industry_outlook_scores"],
        "porters_force_scores": template["porters_force_scores"],
        "eta_quality_scores": template["eta_quality_scores"],
    }


def _assessment_from_ratings(subindustry: str, ratings: dict[str, Any], missing_evidence: list[str]) -> str:
    if missing_evidence:
        return f"Limited current evidence supports a cautious {subindustry} view; missing data keeps the industry assessment conservative."
    repeat = ratings["eta_quality_scores"]["recurring_repeatable_revenue"]["rating"]
    supplier = ratings["porters_force_scores"]["supplier_power"]["rating"]
    entrants = ratings["porters_force_scores"]["threat_of_new_entrants"]["rating"]
    if repeat >= 4 and supplier <= 2:
        return f"Repeat demand supports {subindustry} quality; labor or input scarcity remains the key operating constraint."
    if entrants <= 2:
        return f"Demand can be attractive in {subindustry}; low entry barriers and rivalry limit durable pricing power."
    return f"Current evidence supports a balanced {subindustry} outlook; competition and execution risk remain material."


def _recent_developments_from_text(text: str) -> list[dict[str, str]]:
    developments: list[dict[str, str]] = []
    for term in ["final rule", "recession", "bankruptcy", "shortage", "tariff", "reimbursement"]:
        if term in text:
            developments.append({"type": "material_indicator", "detail": term})
    return developments


def _cap_template_ratings(research: dict[str, Any], maximum: int) -> None:
    for group_name in REQUIRED_DIMENSION_GROUPS:
        for score in research[group_name].values():
            score["rating"] = min(score["rating"], maximum)


def _add_findings(research: dict[str, Any]) -> None:
    for group_name in REQUIRED_DIMENSION_GROUPS:
        for dimension, score in research[group_name].items():
            score.setdefault("finding", score.get("rationale", dimension.replace("_", " ")))


def _static_template_record(template: dict[str, Any]) -> dict[str, Any]:
    record = json.loads(json.dumps(template))
    record["provider"] = "static"
    record["research_status"] = "static_template"
    record["confidence"] = "low" if record.get("confidence") == "high" else record.get("confidence", "medium")
    return record


def _is_cache_valid(record: dict[str, Any], process_date: date) -> bool:
    if record.get("scoring_methodology_version") != SCORING_METHODOLOGY_VERSION:
        return False
    if record.get("material_development_requires_rescore"):
        return False
    next_review = record.get("next_review_date")
    if not next_review:
        return False
    try:
        if date.fromisoformat(next_review) < process_date:
            return False
    except ValueError:
        return False
    for field in ["last_regulatory_check_at", "last_news_check_at"]:
        value = record.get(field)
        if not value:
            return False
        if _date_from_iso(value) < process_date - timedelta(days=7):
            return False
    return True


def _requires_batch_regulatory_check(classification: SubindustryClassification) -> bool:
    return classification.name in {
        "Behavioral Health",
        "Child Care Centers",
        "Financial Services",
        "Healthcare Services",
        "Medical Courier",
        "Physical Therapy",
        "Taxi & Limousine",
    }


def _date_from_iso(value: str) -> date:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def _listing_identity(listing: Listing) -> str:
    return listing.listing_url or f"{listing.source}:{listing.title}"


def _lock_for_cache_key(cache_key: str) -> Lock:
    with _CACHE_LOCK:
        if cache_key not in _CACHE_KEY_LOCKS:
            _CACHE_KEY_LOCKS[cache_key] = Lock()
        return _CACHE_KEY_LOCKS[cache_key]


def _narrowest_defensible(industry: str) -> str:
    broad_map = {
        "Business Services": "B2B Services",
        "Healthcare": "Healthcare Services",
        "Technology & Digital": "Digital Businesses",
        "E-Commerce & Digital": "E-Commerce Businesses",
        "Transportation & Logistics": "Transportation Services",
        "Consumer": "Consumer Services",
    }
    return broad_map.get(industry, industry)


def _base_research(
    *,
    assessment: str,
    confidence: str = "medium",
    research_status: str = "verified",
    current_direction: str = "stable",
    outlook_rating: int = 4,
    momentum_rating: int = 3,
    regulation_rating: int = 3,
    tailwind_rating: int = 4,
    resilience_rating: int = 4,
    disruption_rating: int = 3,
    entrants_rating: int = 3,
    buyer_rating: int = 3,
    supplier_rating: int = 3,
    substitutes_rating: int = 3,
    rivalry_rating: int = 3,
    repeat_rating: int = 4,
    economics_rating: int = 3,
    transferability_rating: int = 3,
    acquisition_supply_rating: int = 4,
    severe_structural_problem: bool = False,
    provider: str = "static",
) -> dict[str, Any]:
    research = {
        "assessment": assessment,
        "confidence": confidence,
        "research_status": research_status,
        "current_direction": current_direction,
        "severe_structural_problem": severe_structural_problem,
        "provider": provider,
        "normalized_subindustry": "",
        "regulatory_geography": "",
        "research_timestamp": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "missing_evidence": [],
        "industry_outlook_scores": {
            "long_term_demand": {"rating": outlook_rating, "weight": 12, "rationale": "Current long-term demand outlook."},
            "current_momentum": {"rating": momentum_rating, "weight": 8, "rationale": "Recent operating momentum."},
            "regulatory_policy": {"rating": regulation_rating, "weight": 8, "rationale": "Current regulatory posture."},
            "structural_tailwinds": {"rating": tailwind_rating, "weight": 4, "rationale": "Structural demand tailwinds."},
            "cyclicality_resilience": {"rating": resilience_rating, "weight": 4, "rationale": "Economic resilience."},
            "disruption_obsolescence": {"rating": disruption_rating, "weight": 4, "rationale": "Disruption and substitution exposure."},
        },
        "porters_force_scores": {
            "threat_of_new_entrants": {"rating": entrants_rating, "weight": 6, "rationale": "Transferable entry barriers."},
            "buyer_power": {"rating": buyer_rating, "weight": 6, "rationale": "Typical customer bargaining power."},
            "supplier_power": {"rating": supplier_rating, "weight": 6, "rationale": "Labor and input availability."},
            "threat_of_substitutes": {"rating": substitutes_rating, "weight": 6, "rationale": "Customer alternatives."},
            "competitive_rivalry": {"rating": rivalry_rating, "weight": 6, "rationale": "Typical competitive intensity."},
        },
        "eta_quality_scores": {
            "recurring_repeatable_revenue": {"rating": repeat_rating, "weight": 8.4, "rationale": "Repeat or contracted demand."},
            "economics_cash_conversion": {"rating": economics_rating, "weight": 8.4, "rationale": "Typical margins, capex and working capital."},
            "transferability_operational_risk": {"rating": transferability_rating, "weight": 7.2, "rationale": "Typical operational transferability."},
            "fragmentation_acquisition_supply": {"rating": acquisition_supply_rating, "weight": 6, "rationale": "Availability of independent acquisition targets."},
        },
        "latest_data_period": "latest reasonably available",
        "sources": [],
    }
    _add_findings(research)
    return research


def _research_templates() -> dict[str, dict[str, Any]]:
    return {
        "Commercial Laundry": _base_research(
            assessment="Contracted repeat demand and route density support attractive economics; equipment needs and local price competition temper the opportunity.",
            entrants_rating=4,
            rivalry_rating=3,
            economics_rating=3,
            repeat_rating=5,
        ),
        "Physical Therapy": _base_research(
            assessment="Demographic demand and repeat visits support growth; clinician scarcity and reimbursement exposure are the main constraints.",
            outlook_rating=5,
            supplier_rating=2,
            transferability_rating=2,
            buyer_rating=2,
        ),
        "Commercial Landscaping": _base_research(
            assessment="Recurring maintenance contracts and acquisition supply are attractive; low entry barriers and labor pressure create meaningful competition.",
            entrants_rating=2,
            supplier_rating=2,
            rivalry_rating=2,
            acquisition_supply_rating=5,
            repeat_rating=4,
        ),
        "Vending Machines & Routes": _base_research(
            assessment="Repeat route revenue and diversified locations are attractive; site-owner bargaining power and low entry barriers require discipline.",
            entrants_rating=2,
            buyer_rating=2,
            repeat_rating=4,
        ),
        "Commercial Printing": _base_research(
            assessment="Repeat B2B demand supports retention, but digital substitutes, equipment investment and price competition limit long-term attractiveness.",
            outlook_rating=2,
            disruption_rating=2,
            substitutes_rating=2,
            rivalry_rating=2,
            economics_rating=2,
        ),
        "Medical Courier": _base_research(
            assessment="Recurring time-critical routes create switching costs; driver availability, insurance requirements and concentrated healthcare buyers can pressure margins.",
            buyer_rating=2,
            supplier_rating=2,
            repeat_rating=5,
            transferability_rating=3,
        ),
        "Digital Marketing Agencies": _base_research(
            assessment="Recurring client work and low capex are attractive; AI disruption, low entry barriers and buyer churn constrain durability.",
            outlook_rating=4,
            disruption_rating=2,
            entrants_rating=2,
            buyer_rating=2,
            rivalry_rating=2,
            economics_rating=4,
        ),
        "E-Commerce Brands": _base_research(
            assessment="Online demand and scalable operations are attractive; platform dependence, paid-media costs and low entry barriers pressure durability.",
            disruption_rating=3,
            entrants_rating=2,
            buyer_rating=2,
            supplier_rating=2,
            rivalry_rating=2,
            economics_rating=3,
        ),
        "SaaS": _base_research(
            assessment="Recurring software revenue and strong cash conversion are attractive; AI disruption and buyer scrutiny require clear differentiation.",
            outlook_rating=5,
            disruption_rating=3,
            entrants_rating=3,
            repeat_rating=5,
            economics_rating=5,
            transferability_rating=4,
        ),
        "Health & Wellness Supplements": _base_research(
            assessment="Wellness demand supports growth, but regulation, platform dependence and crowded brands create meaningful competitive pressure.",
            outlook_rating=4,
            regulation_rating=2,
            entrants_rating=2,
            supplier_rating=2,
            rivalry_rating=2,
        ),
        "Public Relations Agencies": _base_research(
            assessment="Retainer demand can support retention, but client churn, low entry barriers and talent dependence limit industry quality.",
            entrants_rating=2,
            buyer_rating=2,
            supplier_rating=2,
            rivalry_rating=2,
            transferability_rating=2,
        ),
        "Specialty Trade Contractors": _base_research(
            assessment="Required maintenance and skilled trade scarcity support demand; labor dependence and local bidding pressure constrain transferability.",
            tailwind_rating=4,
            entrants_rating=3,
            supplier_rating=2,
            rivalry_rating=2,
            transferability_rating=2,
        ),
    }
