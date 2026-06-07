# EPI First-Use Setup Guidance Design

## Goal

Make installed EPI easier to configure after first install by turning `doctor` dependency warnings into actionable setup guidance.

## Approved Approach

Use the conservative first-use flow:

- `python scripts\orchestrator.py doctor` stays read-only and never opens a browser by default.
- Missing live dependencies still report `warning`, not `error`, so offline fixture dry-runs remain usable.
- Each first-use warning carries structured `setup` guidance in JSON and readable next steps in text output.
- `python scripts\orchestrator.py doctor --open-setup` explicitly opens the setup pages for currently missing dependencies.

## Scope

This change covers:

- `paper_search_cli`: link to upstream `openags/paper-search-mcp` and show the `EPI_PAPER_SEARCH_COMMAND` wrapper path.
- `mineru_token`: link to the MinerU token page and show temporary and persistent PowerShell `MINERU_TOKEN` examples.

This change does not install dependencies, save tokens, call MinerU, run live paper search, or write wiki content.

## Data Contract

`doctor --json` adds:

- `setup_required`: boolean
- `setup_links`: unique setup pages for current warning checks
- per-check `setup`: summary, URL, description, and example commands
- `opened_setup_urls`: only when `--open-setup` is used

## Testing

Tests cover text output, JSON shape, default no-browser behavior, and explicit `--open-setup` behavior with browser opening mocked.
