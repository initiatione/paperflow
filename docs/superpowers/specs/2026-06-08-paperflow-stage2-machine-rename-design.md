# PaperFlow Stage 2 Machine Rename Design

- Date: 2026-06-08
- Status: Approved in conversation for direct hard cut
- Scope: Source-repo machine-facing plugin rename after Stage 1 user-visible naming

## Decision

Stage 2 hard-cuts the source repository to the new plugin identities:

| Concept | Old machine name | New machine name |
| --- | --- | --- |
| Bundle marketplace | `paper-search` | `paperflow` |
| Source preparation plugin | `epi` | `paper-source` |
| Wiki maintenance plugin | `prw` | `paper-wiki` |

The current user base is only the repository owner, so Stage 2 will not keep installable `epi` or `prw` shim plugins. Old names remain only as historical compatibility terms inside artifacts, schema names, Python package names, CLI commands, and documentation where changing them would create unnecessary churn.

## Scope

Stage 2 changes:

- plugin directories: `plugins/epi` -> `plugins/paper-source`, `plugins/PRW` -> `plugins/paper-wiki`
- plugin manifest `name` values: `epi` -> `paper-source`, `prw` -> `paper-wiki`
- marketplace plugin entries and source paths
- source-repo tests that load plugin directories or assert plugin names
- user-facing docs that describe installable plugin names and source paths
- skill metadata where it names the plugin identity

Stage 2 does not change:

- source repository URL/name `paper-search`
- Python package/module namespace `epi`
- `_epi/` vault artifact root
- `wiki-ingest-brief.json`, `wiki_deposition_task.json`, `prw-record-request.json`
- `paper-research-wiki` skill name
- `epi-paper-deposition` compatibility skill name
- MCP package/server names such as `paper-search-mcp`
- installed cache, user runtime config, or local Codex config

## Compatibility Position

No installable shim is created. Existing installed cache may still contain `epi@paper-search` and `prw@paper-search` until the user refreshes/reinstalls the marketplace. Runtime repair is a separate rollout step after this source PR lands.

Docs should say old `epi` / `prw` identifiers are pre-Stage-2 names, not active install targets.

## Acceptance Criteria

- `marketplace.json` and `.agents/plugins/marketplace.json` are named `paperflow` and list `paper-source` and `paper-wiki`.
- `plugins/paper-source/.codex-plugin/plugin.json` has `"name": "paper-source"`.
- `plugins/paper-wiki/.codex-plugin/plugin.json` has `"name": "paper-wiki"`.
- `plugins/epi` and `plugins/PRW` no longer exist in the Stage 2 branch.
- Focused plugin tests pass from the new paths.
- Plugin validator passes for both new plugin roots.
- JSON validation passes for both plugin manifests and both marketplace files.
- Grep guard finds no active marketplace/plugin manifest entries named `epi` or `prw`.
