# 0003: Use Transparent 0-100 Buy-Box Scoring

- Date: 2026-07-23 documented; original decision date unknown.
- Status: Current.

## Decision

Use a simple 100-point buy-box score with plain-English matched and missed criteria.

## Context

The first version must be beginner-friendly and explain why a deal is or is not promising.

## Rationale

Transparent scoring is easier to review and debug than opaque model-only scoring.

## Tradeoffs

The score uses simple rules and substring matching. It is not a full underwriting model.

## Notes

Missing financial information is never guessed and receives zero points for the relevant category.
