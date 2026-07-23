# 0006: Normalize Sub-Industry Output to Approved Labels

- Date: 2026-07-23.
- Status: Current.

## Decision

The industry classifier should write only approved labels from the latest acquisition criteria list into Notion `Sub-industry`.

## Context

Earlier classifier output used useful but non-approved display labels such as SaaS, E-Commerce Brands, and Digital Marketing Agencies.

## Rationale

Using approved labels keeps Notion clean and makes future filtering/reporting more reliable.

## Tradeoffs

Some precise market labels are consolidated into broader approved labels, such as SaaS to `Internet Related` and digital marketing agencies to `Other Business Services`.

## Notes

Tests now check that classifier outputs remain inside the approved taxonomy.
