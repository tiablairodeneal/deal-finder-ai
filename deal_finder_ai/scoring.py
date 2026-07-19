from __future__ import annotations

from deal_finder_ai.models import Listing, ScoreResult


def score_listing(listing: Listing, criteria: dict) -> ScoreResult:
    score = 0
    matched: list[str] = []
    missed: list[str] = []

    industry_score = _industry_score(listing, criteria)
    score += industry_score
    _record(industry_score, 20, "industry matches target list", matched, missed)

    location_score = _location_score(listing, criteria)
    score += location_score
    _record(location_score, 15, "location is New York or remote/online", matched, missed)

    price_score = _range_score(
        listing.asking_price,
        criteria["asking_price"]["min"],
        criteria["asking_price"]["max"],
        "asking price is in the target range",
        matched,
        missed,
        weight=20,
    )
    score += price_score

    cash_flow_score = _range_score(
        listing.cash_flow,
        criteria["cash_flow"]["min"],
        criteria["cash_flow"]["max"],
        "cash flow/SDE/EBITDA is in the target range",
        matched,
        missed,
        weight=25,
    )
    score += cash_flow_score

    financing_score = 10 if listing.seller_financing_offered else 0
    score += financing_score
    _record(financing_score, 10, "seller financing is offered", matched, missed)

    completeness_score = _completeness_score(listing)
    score += completeness_score
    _record(completeness_score, 10, "core listing data is available", matched, missed)

    threshold = int(criteria.get("promising_score_threshold", 75))
    core_fit = industry_score > 0 and location_score > 0 and price_score > 0 and cash_flow_score > 0
    status = "Promising" if score >= threshold and core_fit else "Needs Review"
    explanation = "; ".join(
        [
            f"{score}/100 total",
            "matched: " + ", ".join(matched) if matched else "matched: none",
            "missed: " + ", ".join(missed) if missed else "missed: none",
        ]
    )
    return ScoreResult(score=min(score, 100), explanation=explanation, matched_criteria=matched, missed_criteria=missed, status=status)


def _industry_score(listing: Listing, criteria: dict) -> int:
    if not listing.industry:
        return 0
    listing_industry = listing.industry.lower()
    for target in criteria["target_industries"]:
        if target.lower() in listing_industry or listing_industry in target.lower():
            return 20
    return 0


def _location_score(listing: Listing, criteria: dict) -> int:
    if not listing.location:
        return 0
    location = listing.location.lower()
    remote_terms = [term.lower() for term in criteria["locations"]["remote_terms"]]
    states = [state.lower() for state in criteria["locations"]["states"]]
    if any(term in location for term in remote_terms):
        return 15
    if any(state in location for state in states) or "ny" in location.split():
        return 15
    return 0


def _range_score(
    value: int | None,
    minimum: int,
    maximum: int,
    label: str,
    matched: list[str],
    missed: list[str],
    weight: int,
) -> int:
    if value is None:
        missed.append(label + " (unavailable)")
        return 0
    if minimum <= value <= maximum:
        matched.append(label)
        return weight
    missed.append(label)
    return 0


def _completeness_score(listing: Listing) -> int:
    fields = [
        listing.title,
        listing.listing_url,
        listing.industry,
        listing.location,
        listing.asking_price,
        listing.cash_flow,
    ]
    available = sum(field is not None and field != "" for field in fields)
    return round((available / len(fields)) * 10)


def _record(points: int, max_points: int, label: str, matched: list[str], missed: list[str]) -> None:
    if points == max_points:
        matched.append(label)
    else:
        missed.append(label)
