from __future__ import annotations

from deal_finder_ai.duplicates import duplicate_key
from deal_finder_ai.industry_assessment import assess_listing_industries
from deal_finder_ai.models import EnrichedListing, Listing
from deal_finder_ai.scoring import matched_deal_breaker, score_listing
from deal_finder_ai.summaries import executive_summary


def enrich_listings(listings: list[Listing], criteria: dict) -> list[EnrichedListing]:
    enriched: list[EnrichedListing] = []
    seen: set[str] = set()
    unique_listings: list[tuple[Listing, str]] = []

    for listing in listings:
        if matched_deal_breaker(listing, criteria):
            continue

        key = duplicate_key(listing)
        if key in seen:
            continue
        seen.add(key)
        unique_listings.append((listing, key))

    industry_assessments = assess_listing_industries([listing for listing, _ in unique_listings])
    for listing, key in unique_listings:
        score = score_listing(listing, criteria)
        enriched.append(
            EnrichedListing(
                listing=listing,
                duplicate_key=key,
                score=score,
                executive_summary=executive_summary(listing, score),
                industry_assessment=industry_assessments[listing.listing_url or f"{listing.source}:{listing.title}"],
            )
        )

    return enriched


def qualified_listings(enriched: list[EnrichedListing], criteria: dict) -> list[EnrichedListing]:
    threshold = int(criteria.get("promising_score_threshold", 75))
    return [item for item in enriched if item.score.score >= threshold and item.score.status == "Promising"]
