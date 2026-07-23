# 0004: Separate Industry Assessment from Buy-Box Fit

- Date: 2026-07-23 documented; original decision date unknown.
- Status: Current.

## Decision

Maintain a separate industry assessment with A-D grades and a 100-point internal methodology. Keep the deal-level buy-box score separate.

## Context

A listing can fit price/location/cash-flow criteria while still being in a weaker or higher-risk industry.

## Rationale

Separating industry quality from listing fit makes Notion easier to review and avoids mixing company-specific deal facts with industry-level research.

## Tradeoffs

The system now has two scoring concepts: `Buy Box Score` and `Industry Score`. Documentation and Notion field names must stay clear.

## Notes

Notion receives only `Sub-industry`, `Industry Score`, and `Industry Assessment` from the industry assessment.
