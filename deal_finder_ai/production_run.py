from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from deal_finder_ai.collectors.marketplaces import active_marketplace_names, collect_priority_marketplace_results
from deal_finder_ai.criteria import load_criteria
from deal_finder_ai.notion_sync import NotionSyncError, sync_to_notion_with_counts
from deal_finder_ai.pipeline import enrich_listings, qualified_listings


SUMMARY_DIR = Path(".deal_finder_run")


@dataclass(frozen=True)
class SourceSummary:
    source: str
    collected: int
    mode: str
    note: str


@dataclass(frozen=True)
class ListingSummary:
    title: str
    source: str
    industry: str | None
    subindustry: str | None
    industry_score: str | None
    buy_box_score: int
    status: str
    qualified: bool


@dataclass(frozen=True)
class RunSummary:
    marketplaces_checked: int
    listings_collected: int
    listings_retained: int
    listings_qualified: int
    listings_skipped: int
    notion_created: int
    notion_updated: int
    dry_run: bool
    sources: list[SourceSummary]
    listings: list[ListingSummary]
    errors: list[str]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the hosted production deal finder workflow.")
    parser.add_argument("--max-per-source", type=int, default=int(os.getenv("DEAL_FINDER_MAX_PER_SOURCE", "10")))
    parser.add_argument("--dry-run", action="store_true", help="Collect and score listings without writing to Notion.")
    parser.add_argument("--summary-path", default=str(SUMMARY_DIR / "run_summary.json"))
    args = parser.parse_args()

    _validate_required_environment(dry_run=args.dry_run)
    criteria = load_criteria()
    source_results = collect_priority_marketplace_results(max_per_source=args.max_per_source)
    listings = [listing for result in source_results for listing in result.listings]
    enriched = enrich_listings(listings, criteria)
    qualified = qualified_listings(enriched, criteria)
    skipped = max(len(listings) - len(enriched), 0)
    errors = [
        f"{result.source}: {result.note}"
        for result in source_results
        if result.mode.startswith("skipped") or "error" in result.mode.lower()
    ]

    notion_created = 0
    notion_updated = 0
    if not args.dry_run:
        try:
            notion_result = sync_to_notion_with_counts(qualified)
            notion_created = notion_result.created_pages
            notion_updated = notion_result.updated_pages
        except NotionSyncError as error:
            errors.append(str(error))
            _write_summary(
                args.summary_path,
                _summary(source_results, listings, enriched, qualified, skipped, notion_created, notion_updated, args.dry_run, errors),
            )
            raise

    summary = _summary(source_results, listings, enriched, qualified, skipped, notion_created, notion_updated, args.dry_run, errors)
    _write_summary(args.summary_path, summary)
    _print_summary(summary)
    return 0


def _validate_required_environment(*, dry_run: bool) -> None:
    missing = []
    if not dry_run:
        for name in ["NOTION_TOKEN", "NOTION_DEALS_DATABASE_ID"]:
            if not os.getenv(name):
                missing.append(name)
    if missing:
        joined = ", ".join(missing)
        raise SystemExit(f"Missing required repository secret(s) or environment values: {joined}")


def _summary(
    source_results,
    listings,
    enriched,
    qualified,
    skipped: int,
    notion_created: int,
    notion_updated: int,
    dry_run: bool,
    errors: list[str],
) -> RunSummary:
    return RunSummary(
        marketplaces_checked=len(active_marketplace_names()),
        listings_collected=len(listings),
        listings_retained=len(enriched),
        listings_qualified=len(qualified),
        listings_skipped=skipped,
        notion_created=notion_created,
        notion_updated=notion_updated,
        dry_run=dry_run,
        sources=[
            SourceSummary(source=result.source, collected=len(result.listings), mode=result.mode, note=result.note)
            for result in source_results
        ],
        listings=[
            ListingSummary(
                title=item.listing.title,
                source=item.listing.source,
                industry=item.listing.industry,
                subindustry=item.industry_assessment.subindustry if item.industry_assessment else None,
                industry_score=item.industry_assessment.grade if item.industry_assessment else None,
                buy_box_score=item.score.score,
                status=item.score.status,
                qualified=item in qualified,
            )
            for item in enriched
        ],
        errors=errors,
    )


def _write_summary(path: str, summary: RunSummary) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(asdict(summary), indent=2, sort_keys=True), encoding="utf-8")


def _print_summary(summary: RunSummary) -> None:
    print("Deal Finder production run summary")
    print(f"Listings collected: {summary.listings_collected}")
    print(f"Listings retained after exclusions and deduplication: {summary.listings_retained}")
    print(f"Listings qualified: {summary.listings_qualified}")
    print(f"Notion records created: {summary.notion_created}")
    print(f"Notion records updated: {summary.notion_updated}")
    print(f"Listings skipped: {summary.listings_skipped}")
    print(f"Dry run: {summary.dry_run}")
    print("Sources:")
    for source in summary.sources:
        print(f"- {source.source}: {source.collected} listings ({source.mode}) - {source.note}")
    print("Listings by classified sub-industry:")
    if summary.listings:
        for listing in summary.listings:
            marker = "qualified" if listing.qualified else "not qualified"
            print(
                f"- {listing.source}: {listing.title} | industry: {listing.industry or 'Unavailable'} | "
                f"sub-industry: {listing.subindustry or 'Unavailable'} | buy-box score: {listing.buy_box_score} | "
                f"{listing.status} | {marker}"
            )
    else:
        print("- none")
    if summary.errors:
        print("Errors or skipped sources:")
        for error in summary.errors:
            print(f"- {error}")
    else:
        print("Errors or skipped sources: none")


if __name__ == "__main__":
    raise SystemExit(main())
