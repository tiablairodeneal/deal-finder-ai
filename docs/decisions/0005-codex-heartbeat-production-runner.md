# 0005: Codex Heartbeat Is the Production Daily Runner

- Date: 2026-07-23.
- Status: Current.

## Decision

Keep the scheduled daily production run as a Codex thread heartbeat using the local Mac workspace and connected Notion connector/OAuth.

## Context

A hosted GitHub Actions schedule was considered and a manual-only workflow remains available for safe tests, but production scheduling currently stays in Codex.

## Rationale

The heartbeat can use the connected Notion connector without requiring standalone Notion credentials in repository or GitHub secrets for daily production.

## Tradeoffs

The daily run depends on the user’s Mac being awake, online, and available with Codex running and the workspace path intact.

## Notes

Do not enable a second scheduled daily runner while this heartbeat is active.
