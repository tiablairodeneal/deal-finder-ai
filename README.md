# Deal Finder AI

This is a small first version of an AI-powered business acquisition deal finder.

The important design choice: **Notion is the only database and CRM**. This project does not use Supabase or any other database. The code collects listings, scores them, removes duplicates, and sends qualified deals to Notion.

## What v1 Does

- Uses your acquisition criteria from `acquisition_criteria.json`
- Starts with one marketplace: BizQuest
- Uses realistic sample listings for the first safe demo workflow
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
- Promising score: 75+

Edit `acquisition_criteria.json` when your thesis changes.

## Install

This starter uses only the Python standard library for the core workflow.

To run tests, install pytest if needed:

```bash
python -m pip install pytest
```

## Run The Demo

```bash
python run_demo.py
```

This prints collected listings, duplicate handling, scores, and summaries.

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

## Why BizQuest First

Your marketplace spreadsheet includes many good sources, but v1 should start with one practical public source. BizQuest is a good first candidate because its listings are public, broad, and often include asking price and cash flow fields.

For now, the collector uses sample data. Live collection should be added carefully and only for public pages that allow automation. Do not bypass logins, paywalls, CAPTCHAs, robots.txt, or other protections.

## Roadmap

1. Add a respectful live BizQuest collector for allowed public listing pages.
2. Add a daily run that saves new qualified deals to Notion.
3. Add a daily digest view or message from Notion records.
4. Add marketplace-specific collectors one at a time.
5. Add richer summaries with an AI model after the data pipeline is stable.
6. Add review outcomes in Notion so future scoring can learn from your feedback.
