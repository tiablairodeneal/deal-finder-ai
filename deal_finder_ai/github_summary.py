from __future__ import annotations

import json
from pathlib import Path


def markdown_from_summary(summary_path: str) -> str:
    summary = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    lines = [
        "## Deal Finder Run Summary",
        "",
        f"- Listings collected: {summary['listings_collected']}",
        f"- Listings retained after exclusions and deduplication: {summary['listings_retained']}",
        f"- Listings qualified: {summary['listings_qualified']}",
        f"- Notion records created: {summary['notion_created']}",
        f"- Notion records updated: {summary['notion_updated']}",
        f"- Listings skipped: {summary['listings_skipped']}",
        f"- Dry run: {summary['dry_run']}",
        "",
        "### Sources",
    ]
    for source in summary["sources"]:
        lines.append(f"- {source['source']}: {source['collected']} listings ({source['mode']})")
    lines.extend(["", "### Listings By Classified Sub-Industry"])
    if summary["listings"]:
        for listing in summary["listings"]:
            marker = "qualified" if listing["qualified"] else "not qualified"
            lines.append(
                f"- {listing['source']}: {listing['title']} | "
                f"industry: {listing['industry'] or 'Unavailable'} | "
                f"sub-industry: {listing['subindustry'] or 'Unavailable'} | "
                f"buy-box score: {listing['buy_box_score']} | {listing['status']} | {marker}"
            )
    else:
        lines.append("- none")
    if summary["errors"]:
        lines.extend(["", "### Errors or skipped sources"])
        lines.extend(f"- {error}" for error in summary["errors"])
    return "\n".join(lines) + "\n"


def main() -> int:
    summary_path = ".deal_finder_run/run_summary.json"
    github_summary = Path(__import__("os").environ.get("GITHUB_STEP_SUMMARY", ""))
    markdown = markdown_from_summary(summary_path)
    if github_summary:
        with github_summary.open("a", encoding="utf-8") as handle:
            handle.write(markdown)
    else:
        print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
