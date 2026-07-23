# Automation

## Current Production Runner

The current scheduled production runner is a Codex thread heartbeat named `daily-deal-finder`.

Schedule:

- Every day at 9:00 a.m. `America/New_York`.
- Timezone-aware rule: `DTSTART;TZID=America/New_York:20260724T090000` with `RRULE:FREQ=DAILY`.
- This is intended to follow Eastern Standard Time and Eastern Daylight Time automatically.

Do not change, disable, or delete this heartbeat unless the user explicitly asks.

## Production Execution Path

The heartbeat prompt instructs Codex to:

1. Use the local repository at `/Users/tialewis/Documents/Codex/2026-07-19/work-in-my-github-repository-tiablairodeneal/deal-finder-ai`.
2. Run tests first.
3. Collect live public listings only from allowed/public sources.
4. Exclude FedEx route listings and Amazon FBA businesses.
5. Score, classify, deduplicate, and identify qualified listings using repository logic.
6. Refresh matching rows or create qualified rows in the existing Notion deals database through the connected Notion connector/OAuth.
7. Summarize counts, live sources, skipped sources, Notion rows refreshed/created, classified sub-industries, qualified listings, and errors.

The heartbeat path should not require standalone `NOTION_TOKEN` or `NOTION_DEALS_DATABASE_ID` credentials.

## Operational Requirements

Because the production runner is local to Codex:

- The user’s Mac must be awake.
- The Mac must be online.
- Codex must be available.
- The local workspace path must still exist.
- The connected Notion connector/OAuth must remain authorized.
- Public marketplace pages must remain safely fetchable.

If any of those conditions fail, the daily run can fail or skip work.

## Duplicate Run Prevention

Production daily scheduling is centralized in the Codex heartbeat. GitHub Actions is manual-only and has no daily schedule. Do not activate a second scheduled production runner while the heartbeat remains active.

Within the repository logic:

- In-memory duplicate detection removes duplicates inside a run.
- `Duplicate Key` is used in Notion/Python API sync paths to update matching records rather than creating duplicates.
- The heartbeat prompt instructs Codex to refresh matching Notion rows before creating new qualified rows.

## Manual Test Procedure

Safe no-write test:

```bash
DEAL_FINDER_RESEARCH_PROVIDER=static python -m deal_finder_ai.production_run --dry-run --max-per-source 1 --summary-path .deal_finder_run/local_heartbeat_dry_run_summary.json
```

This collects, filters, scores, deduplicates, classifies, and summarizes without writing to Notion.

Run tests:

```bash
python -m unittest discover -s tests
```

Manual GitHub Actions can also run dry-run tests from the `Daily Deal Finder` workflow. It is not scheduled and should not be used as the daily production runner while the Codex heartbeat is active.

## Failure Behavior

The production-style CLI writes a JSON summary under `.deal_finder_run/` and prints concise counts. Skipped sources and errors are reported. Generated run artifacts are ignored by git.

The Python Notion API path has timeout and retry settings:

- `DEAL_FINDER_NOTION_TIMEOUT_SECONDS`, default `30`.
- `DEAL_FINDER_NOTION_RETRIES`, default `2`.

Scraper and research timeout/retry settings are configured by environment variables in the manual GitHub Actions workflow and can also be used locally.

## Known Limitation

The heartbeat production path depends on Codex’s connected Notion connector. The checked-in Python Notion API integration is still present for manual/API use and requires token environment variables when used directly.
