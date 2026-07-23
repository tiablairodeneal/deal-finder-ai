# Deal Finder AI

This is a small first version of an AI-powered business acquisition deal finder.

The important design choice: **Notion is the only database and CRM**. This project does not use Supabase or any other database. The code collects listings, scores them, removes duplicates, and sends qualified deals to Notion.

## What v1 Does

- Uses your acquisition criteria from `acquisition_criteria.json`
- Starts with your priority marketplace list
- Uses live public listing pages where practical, with sample data kept for tests and demos
- Scores every listing from 0 to 100
- Explains each score in plain English
- Classifies each listing into a standardized sub-industry
- Adds an internal ETA industry assessment with Porter’s Five Forces
- Removes duplicates using the listing URL first
- Marks missing financial data as unavailable instead of guessing
- Generates a short executive summary
- Can save qualified deals to your Notion deals database

## Notion Database

Created private Notion database:

https://app.notion.com/p/e0f23824e98d4e459c3466c05e767239

Main fields:

- Deal Name
- Source
- Listing URL
- Industry
- Location
- Asking Price
- Annual Revenue
- Cash Flow / SDE / EBITDA
- Seller Financing Offered
- Industry Score
- Buy Box Score
- Status
- Date Found
- Last Seen
- Sub-industry
- Industry Assessment

`Duplicate Key` is kept as a hidden operations field so the Notion sync can update existing rows instead of creating duplicates.

`Industry Score` is written to Notion as the industry-level letter grade: `A`, `B`, `C`, or `D`. The original listing/deal score is still calculated internally and remains visible in `Buy Box Score`.

Views created:

- Qualified Deals
- Promising Deals
- Needs Review
- Duplicates
- By Industry
- By Source

## Your Acquisition Criteria

- Industries and sub-industries: expanded list across business services, professional services, real estate services, construction/building services, consumer products and services, education and training, food and beverage, healthcare and wellness, home and garden, hospitality/entertainment/leisure, industrials/manufacturing, media/communications, technology/digital, and transportation/logistics
- Location: New York State or fully online/remote
- Asking price: $1M to $6M
- Cash flow/SDE: $500k to $2M
- Seller financing: positive signal, not required
- Deal breakers: FedEx route listings and Amazon FBA businesses
- Promising score: 75+

Edit `acquisition_criteria.json` when your thesis changes.

## Install

This starter uses only the Python standard library for the core workflow.

No package install is needed to run the demo or tests.

## Run The Deal Finder

```bash
python run_demo.py
```

By default, this checks live public marketplace pages where practical. It prints source-by-source collection notes, duplicate handling, scores, and summaries.

For a repeatable offline sample run:

```bash
python run_demo.py --sample-only
```

## Run Tests

```bash
python -m unittest discover -s tests -v
```

## Save To Notion

Create a Notion integration token, share the Notion database with that integration, then set:

```bash
export NOTION_TOKEN="secret_your_notion_integration_token"
export NOTION_DEALS_DATABASE_ID="e0f23824e98d4e459c3466c05e767239"
python run_demo.py --sync-notion
```

The sync checks existing Notion duplicate keys before creating new records.

## Hosted Daily Automation

The production daily run is hosted in GitHub Actions at `.github/workflows/daily-deal-finder.yml`.

It runs the same repository workflow as the local command:

1. Run the automated tests.
2. Collect live public listings from the configured sources.
3. Apply exclusions, scoring, industry assessment, and duplicate detection.
4. Create or update qualified records in the same Notion deals database.

The workflow is scheduled for **9:00 a.m. America/New_York every day**. GitHub Actions schedules are written in UTC, so the workflow registers both UTC times that can map to 9:00 a.m. New York:

- `13:00 UTC` during Eastern Daylight Time
- `14:00 UTC` during Eastern Standard Time

A local-time guard inside the job checks `America/New_York` and skips the non-matching trigger. This keeps the run at 9:00 a.m. New York time when daylight saving time changes.

### Required GitHub Repository Secrets

Configure these in GitHub:

`Settings` -> `Secrets and variables` -> `Actions` -> `Repository secrets`

- `NOTION_TOKEN`
- `NOTION_DEALS_DATABASE_ID`

The current live research provider and public scrapers do not require paid API credentials. If a future research provider or scraper requires credentials, add them as repository secrets and pass them to the workflow as environment variables. Do not commit credential values.

### Manual Run

In GitHub, open:

`Actions` -> `Daily Deal Finder` -> `Run workflow`

Inputs:

- `dry_run=true`: safe test mode that collects, scores, deduplicates, and summarizes without writing to Notion.
- `dry_run=false`: production mode that creates or updates qualified deals in Notion.
- `max_per_source`: reduce this for a smaller test run.

The workflow uses GitHub Actions concurrency so only one production run can execute at a time. This prevents overlapping scheduled/manual runs from creating duplicate rows.

### Monitoring Failures

Each run writes a concise GitHub Actions summary with:

- Listings collected
- Listings retained after exclusions and deduplication
- Listings qualified
- Notion records created
- Notion records updated
- Listings skipped
- Errors or failed sources

If a run fails, GitHub uploads non-secret run artifacts from `.deal_finder_run/` and `.deal_finder_cache/` for troubleshooting. Secret values are not printed by the workflow.

### Cache Persistence

Industry research records are restored and saved with `actions/cache` from `.deal_finder_cache`. The cache key includes the operating system and `acquisition_criteria.json`, so normal runs reuse useful research while criteria changes can start a fresh cache.

## Scoring System

The listing/deal score is intentionally transparent:

- Industry match: 20 points
- Location match: 15 points
- Asking price in range: 20 points
- Cash flow/SDE/EBITDA in range: 25 points
- Seller financing mentioned: 10 points
- Core data completeness: 10 points

Missing financial information gets 0 points for that category and is labeled unavailable.

A listing is only marked Promising when it reaches the score threshold and passes the core fit checks: industry, location, asking price, and cash flow/SDE/EBITDA.

## Industry Assessment

Each enriched listing also receives an industry-level assessment using `eta-industry-v1`.

The internal score is 0 to 100:

- Industry Outlook: 40 points
- Porter’s Five Forces: 30 points
- ETA Operating and Acquisition Quality: 30 points

The numeric score, component scores, source notes, confidence, dates, and cache metadata stay internal. Notion receives only:

- `Sub-industry`: standardized title case, such as `Commercial Laundry` or `Digital Marketing Agencies`
- `Industry Score`: one letter only, `A`, `B`, `C`, or `D`
- `Industry Assessment`: one sentence, capped at 35 words

The assessor does not use listing-specific revenue, SDE, asking price, valuation multiple, margins, or customer concentration when assigning the industry grade. Those stay part of separate company-level diligence.

Research records are cached in `.deal_finder_cache/industry_research_cache.json` by sub-industry, regulatory geography, and methodology version. The cache is ignored by git. Stale records, methodology mismatches, and materially different regulatory geographies trigger a fresh assessment.

### Research Provider Configuration

Production defaults to the live research provider. It only runs when live public research is explicitly enabled:

```bash
export DEAL_FINDER_RESEARCH_PROVIDER="live"
export DEAL_FINDER_LIVE_RESEARCH_ENABLED="1"
```

The live provider uses public authoritative sources such as BLS, Census, BEA, Federal Register, and relevant state regulator pages. It does not use broker listings or marketplaces as primary evidence and does not claim access to paid reports such as IBISWorld.

Optional controls:

```bash
export DEAL_FINDER_RESEARCH_TIMEOUT_SECONDS="12"
export DEAL_FINDER_RESEARCH_RETRIES="1"
export DEAL_FINDER_INDUSTRY_CACHE_PATH=".deal_finder_cache/industry_research_cache.json"
```

For deterministic local development only:

```bash
export DEAL_FINDER_RESEARCH_PROVIDER="static"
```

Static output is marked internally as `static_template`, not current verified research. If live research is selected but not enabled or unavailable, the batch continues with a conservative provisional assessment no better than `C`; the issue is logged and the invalid/provisional result is not cached as verified research.

Current live research uses public pages, so there are no direct API costs. Keep requests modest: cache results, use the default timeout/retry settings, and avoid reprocessing stale-free cache keys unnecessarily.

## Priority Marketplaces

The current workflow checks these sources from the deal-flow spreadsheet when they expose public listing pages that are practical to fetch:

- AcquisitionsDirect
- AppBusinessBrokers
- Axial
- BizBuySell
- BizQuest
- BusinessBroker
- BusinessesForSale
- BusinessExits
- BusinessMart
- FirstChoice Business Brokers
- LINK
- Merge
- QuietLight
- SMERGERS
- Transferslot
- Website Closers

The live job only reads public pages that are practical to fetch respectfully.

- Live public listing cards or rows: BusinessBroker, BusinessExits, BusinessMart, LINK, Merge, QuietLight, SMERGERS, Transferslot, Website Closers
- Live public structured listing data: BusinessesForSale
- Live public detail links when visible: AcquisitionsDirect
- Public page checked, no static listing details currently exposed: AppBusinessBrokers, FirstChoice Business Brokers
- Skipped when blocked from this runtime: BizBuySell, BizQuest
- Skipped because login-gated or not a public listing marketplace: Axial and spreadsheet sources such as private networks, Facebook groups, education products, legal/lender tools, and paid/proprietary data platforms
- Skipped when robots.txt cannot be checked or does not safely allow fetching: DealStream, Motion Invest, Tiny Acquisitions, and any similar source until an approved export, API, or public fetch path is available

Do not bypass logins, paywalls, CAPTCHAs, robots.txt, bot blocks, or other protections. Sample data remains available for local tests with `python run_demo.py --sample-only`.

## Roadmap

1. Add respectful live collectors one source at a time, starting with the public sources that expose enough financial data.
2. Add a daily run that saves new qualified deals to Notion.
3. Add a daily digest view or message from Notion records.
4. Add marketplace-specific collectors one at a time.
5. Add richer summaries with an AI model after the data pipeline is stable.
6. Add review outcomes in Notion so future scoring can learn from your feedback.
