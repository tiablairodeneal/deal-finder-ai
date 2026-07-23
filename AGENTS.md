# Agent Instructions

These instructions apply to Codex agents and other AI coding assistants working in this repository.

## Standing Rules

- Before making changes, read the repository documentation relevant to the task. Start with `README.md`, `docs/PROJECT_CONTEXT.md`, `docs/ACQUISITION_CRITERIA.md`, `docs/INDUSTRY_SCORING.md`, `docs/AUTOMATION.md`, and relevant files under `docs/decisions/`.
- Preserve the existing architecture unless the user explicitly instructs otherwise.
- Keep Notion as the source of truth for deals. Do not add Supabase, another database, a duplicate CRM, a parallel scraper system, or a duplicate automation workflow without explicit approval.
- Never commit credentials, tokens, secrets, private seller information, local `.env` files, temporary caches, run artifacts, or local machine state.
- Treat documentation updates as part of completing every material project task, not as a separate optional follow-up.
- Update relevant documentation whenever behavior, architecture, acquisition criteria, industry taxonomy, scoring methodology, integrations, dependencies, operating requirements, known limitations, Notion properties, marketplace sources, or automation changes.
- Run appropriate tests before committing. For normal code changes, run the complete unit test suite.
- Clearly report unresolved limitations, skipped sources, operational requirements, and any manual follow-up.
- Do not bypass logins, paywalls, CAPTCHAs, robots.txt, bot blocks, or other marketplace protections.
- Never guess missing listing financials. Leave unavailable values empty or mark them unavailable in explanations.

## Orientation

Start with:

1. `README.md`
2. `docs/PROJECT_CONTEXT.md`
3. `docs/ACQUISITION_CRITERIA.md`
4. `docs/INDUSTRY_SCORING.md`
5. `docs/AUTOMATION.md`
6. Relevant files under `docs/decisions/`
7. `docs/worklog/`

## Documentation Maintenance

Documentation is required when a task materially changes the project. A material change includes any change to:

- System behavior or user-visible workflow.
- Architecture or data flow.
- Acquisition criteria or industry taxonomy.
- Buy-box scoring or industry scoring methodology.
- Marketplace scraping sources or collection rules.
- Notion integration, properties, or sync behavior.
- Automation, scheduling, credentials model, or operating requirements.
- Dependencies, setup, test procedure, or known limitations.

For material changes:

- Update the corresponding permanent documentation in the same commit whenever practical.
- Add or update a decision record under `docs/decisions/` when the change represents a meaningful architecture, integration, automation, scoring, or methodology decision.
- Add a concise dated entry to the current monthly file under `docs/worklog/`.
- Compare the implementation with the affected documentation before finishing.
- Confirm the documentation accurately reflects production behavior.

Do not update permanent documentation for tasks with no material project change. Do not create repetitive worklog entries for minor formatting, exploratory checks, failed attempts with no lasting impact, routine commands, or other non-material work.

## Before Committing

- Check `git status` and avoid including generated files.
- Confirm `.deal_finder_cache/`, `.deal_finder_run/`, `.env`, secrets, and Python bytecode are not staged.
- Run `python -m unittest discover -s tests`.
- Run `git diff --check`.
- For each material task, confirm documentation changes are included in the same commit as related code changes whenever practical.
- Summarize files changed, tests run, discrepancies found, and limitations that remain.

## Final Task Reports

Every final report for a material task must state:

- Which permanent documentation files were updated.
- Whether a worklog entry or decision record was added or updated.
- Tests and validation performed.
- Commit identifier and push status.
- Any unresolved mismatch between documentation and production behavior.

If no documentation update is appropriate, explicitly state: "Documentation reviewed; no material update required."
