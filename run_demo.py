from __future__ import annotations

import argparse

from deal_finder_ai.collectors.marketplaces import active_marketplace_names, collect_priority_marketplace_samples
from deal_finder_ai.criteria import load_criteria
from deal_finder_ai.notion_sync import NotionSyncError, sync_to_notion
from deal_finder_ai.pipeline import enrich_listings, qualified_listings


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the deal finder sample workflow.")
    parser.add_argument("--sync-notion", action="store_true", help="Save qualified deals to Notion using NOTION_TOKEN.")
    args = parser.parse_args()

    criteria = load_criteria()
    listings = collect_priority_marketplace_samples()
    enriched = enrich_listings(listings, criteria)
    qualified = qualified_listings(enriched, criteria)

    print(f"Checked {len(active_marketplace_names())} priority marketplaces.")
    print(f"Collected {len(listings)} sample listings.")
    print(f"Kept {len(enriched)} unique listings after duplicate detection.")
    print(f"{len(qualified)} listings scored {criteria['promising_score_threshold']}+.")
    print()

    for item in enriched:
        listing = item.listing
        print(f"{item.score.score:3d} | {item.score.status:12s} | {listing.title}")
        print(f"      {item.score.explanation}")

    if args.sync_notion:
        try:
            created = sync_to_notion(qualified)
        except NotionSyncError as error:
            print(f"\nNotion sync skipped: {error}")
            return 1
        print(f"\nCreated {len(created)} Notion pages.")
        for url in created:
            print(url)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
