# 0002: Collect Only Safe Public Marketplace Pages

- Date: 2026-07-23 documented; original decision date unknown.
- Status: Current.

## Decision

Collectors may read public listing pages that are practical and safe to fetch. They must skip login-gated, paywalled, CAPTCHA-protected, blocked, or robots-disallowed sources.

## Context

The target marketplace list includes both public websites and sources that may be blocked or require accounts.

## Rationale

This reduces compliance and operational risk while keeping the first version useful.

## Tradeoffs

Some high-value sources will produce zero rows until an approved export, API, or permitted integration exists.

## Notes

Axial is currently login-gated. BizBuySell and BizQuest are skipped when blocked or when robots.txt cannot be safely checked.
