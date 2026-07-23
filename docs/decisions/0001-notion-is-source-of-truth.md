# 0001: Notion Is the Deal Source of Truth

- Date: 2026-07-23 documented; original decision date unknown.
- Status: Current.

## Decision

Use Notion as the only database and CRM for deal records.

## Context

The project stores qualified acquisition opportunities in a Notion deals database. The repository contains code, criteria, scoring rules, and documentation, but not a separate deal database.

## Rationale

This keeps the first version simple and keeps deal review, status, and CRM activity in one place.

## Tradeoffs

The project does not get database features such as SQL querying, row-level constraints, or server-side jobs. Notion availability and connector/API behavior matter operationally.

## Notes

Do not add Supabase or another database without explicit approval.
