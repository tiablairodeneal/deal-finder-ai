# Agent Instructions

These instructions apply to Codex agents and other AI coding assistants working in this repository.

## Standing Rules

- Read `README.md` and the files in `docs/` before making changes.
- Preserve the existing architecture unless the user explicitly instructs otherwise.
- Keep Notion as the source of truth for deals. Do not add Supabase, another database, a duplicate CRM, a parallel scraper system, or a duplicate automation workflow without explicit approval.
- Never commit credentials, tokens, secrets, private seller information, local `.env` files, temporary caches, run artifacts, or local machine state.
- Update relevant documentation whenever behavior, acquisition criteria, scoring, integrations, Notion properties, marketplace sources, or automation changes.
- Run appropriate tests before committing. For normal code changes, run the complete unit test suite.
- Clearly report unresolved limitations, skipped sources, operational requirements, and any manual follow-up.
- Do not bypass logins, paywalls, CAPTCHAs, robots.txt, bot blocks, or other marketplace protections.
- Never guess missing listing financials. Leave unavailable values empty or mark them unavailable in explanations.

## Orientation

Start with:

1. `docs/PROJECT_CONTEXT.md`
2. `docs/ACQUISITION_CRITERIA.md`
3. `docs/INDUSTRY_SCORING.md`
4. `docs/AUTOMATION.md`
5. `docs/decisions/`
6. `docs/worklog/`

## Before Committing

- Check `git status` and avoid including generated files.
- Confirm `.deal_finder_cache/`, `.deal_finder_run/`, `.env`, secrets, and Python bytecode are not staged.
- Run `python -m unittest discover -s tests`.
- Run `git diff --check`.
- Summarize files changed, tests run, discrepancies found, and limitations that remain.
