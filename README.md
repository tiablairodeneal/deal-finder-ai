# Deal Finder AI

This is a small first version of an AI-powered business acquisition deal finder.

The important design choice: **Notion is the only database and CRM**. This project does not use Supabase or any other database. The code collects listings, scores them, removes duplicates, and sends qualified deals to Notion.

## What v1 Does

- Uses your acquisition criteria from `acquisition_criteria.json`
- Starts with your priority marketplace list
- Uses live public listing pages where practical, with sample data kept for tests and demos
- Scores every listing from 0 to 100
- Explains each score in plain English
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
- Financing
- Seller Financing Offered
- Score
- Score Explanation
- Status
- Duplicate Key
- Executive Summary
- Date Found
- Last Seen

Views created:

- Qualified Deals
- Promising Deals
- Needs Review
- Duplicates
- By Industry
- By Source

## Your Starting Criteria

- Industries: broad list including services, construction, healthcare, digital, transportation, media, consumer, and industrial categories
- Location: New York State or fully online/remote
- Asking price: $1M to $6M
- Cash flow/SDE: $500k to $2M
- Seller financing: positive signal, not required
- Deal breakers: FedEx route listings, including FedEx P&D and pickup/delivery route listings
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

## Scoring System

The score is intentionally transparent:

- Industry match: 20 points
- Location match: 15 points
- Asking price in range: 20 points
- Cash flow/SDE/EBITDA in range: 25 points
- Seller financing mentioned: 10 points
- Core data completeness: 10 points

Missing financial information gets 0 points for that category and is labeled unavailable.

A listing is only marked Promising when it reaches the score threshold and passes the core fit checks: industry, location, asking price, and cash flow/SDE/EBITDA.

## Priority Marketplaces

The current workflow checks these priority sources:

- AcquisitionsDirect
- AppBusinessBrokers
- Axial
- BizBuySell
- BizQuest
- FirstChoice Business Brokers
- Merge
- QuietLight
- Website Closers

The live job only reads public pages that are practical to fetch respectfully.

- Live public listing cards: Merge, QuietLight, Website Closers
- Live public detail links when visible: AcquisitionsDirect
- Public page checked, no static listing details currently exposed: AppBusinessBrokers, FirstChoice Business Brokers
- Skipped when blocked from this runtime: BizBuySell, BizQuest
- Skipped because login-gated: Axial

Do not bypass logins, paywalls, CAPTCHAs, robots.txt, bot blocks, or other protections. Sample data remains available for local tests with `python run_demo.py --sample-only`.

## Roadmap

1. Add respectful live collectors one source at a time, starting with the public sources that expose enough financial data.
2. Add a daily run that saves new qualified deals to Notion.
3. Add a daily digest view or message from Notion records.
4. Add marketplace-specific collectors one at a time.
5. Add richer summaries with an AI model after the data pipeline is stable.
6. Add review outcomes in Notion so future scoring can learn from your feedback.
