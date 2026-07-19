from __future__ import annotations

from deal_finder_ai.duplicates import duplicate_key
from deal_finder_ai.models import EnrichedListing, Listing
from deal_finder_ai.scoring import score_listing
from deal_finder_ai.summaries import executive_summary


def enrich_listings(listings: list[Listing], criteria: dict) -> list[EnrichedListing]:
    enriched: list[EnrichedListing] = []
    seen: set[str] = set()

    for listing in listings:
        key = duplicate_key(listing)
        if key in seen:
            continue
        seen.add(key)

        score = score_listing(listing, criteria)
        enriched.append(
            EnrichedListing(
                listing=listing,
                duplicate_key=key,
                score=score,
                executive_summary=executive_summary(listing, score),
            )
        )

    return enriched


def qualified_listings(enriched: list[EnrichedListing], criteria: dict) -> list[EnrichedListing]:
    threshold = int(criteria.get("promising_score_threshold", 75))
    return [item for item in enriched if item.score.score >= threshold and item.score.status == "Promising"]
