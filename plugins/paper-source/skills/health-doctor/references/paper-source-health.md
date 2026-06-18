# Paper Source Health

Use this reference when the failing layer is Paper Source itself: plugin discovery, skill bundle health, profile/config, runtime.json, provider readiness, MinerU, EasyScholar, Zotero, or installed-cache freshness.

## Health Layers

1. Source checkout: manifest, `skills/routing.yaml`, skill folders, UI metadata, wrappers, docs, and tests.
2. Installed runtime: the marketplace-installed plugin cache that Codex actually loaded for the current session.
3. Vault config: `<vault>/_paper_source/meta/paper-source-config.yaml` and config state/history.
4. User runtime: the user-level Paper Source `runtime.json` and referenced env files.
5. External tools: `paper-search-mcp`, `paper-search` CLI, optional `grok-search-rs`, MinerU, EasyScholar, and Zotero.

Keep these layers separate in reports. Passing tests in a source checkout does not prove the installed runtime has been refreshed or loaded by the current Codex session.

## First Checks

Run:

```powershell
python scripts\orchestrator.py doctor --vault <vault> --json
python scripts\orchestrator.py config-status --vault <vault> --json --include-values --include-runtime
```

Interpretation:

- `status=ok` with warnings usually means the plugin structure is usable and only optional providers are missing.
- Plugin structure, routing, missing skill metadata, or wrapper failures are plugin health issues.
- Missing profile/config blocks normal paper workflows; route to `config-setup`.
- Missing provider env vars are readiness gaps, not proof that no papers exist.
- MinerU or EasyScholar missing should not block read-only discovery or configuration checks.

## Runtime Config Boundary

Runtime config records commands and env-file paths, not secrets. It should not depend on a development checkout, project `.env`, vault internals, temp directories, or versioned installed cache paths.

Report sensitive fields as `set`, `missing`, or `redacted` only. Common secret-bearing vars include:

- `MINERU_TOKEN`
- `EASYSCHOLAR_SECRET_KEY`
- `OPENAI_COMPATIBLE_API_KEY`
- `PAPER_SEARCH_MCP_*_API_KEY`
- provider access tokens

Common non-secret diagnostics include OpenAI-compatible base URL presence, model name, command path, `cwd`, args shape, env-file existence, and provider readiness flags.

## Dependency Guide

- `paper-search-mcp`: broad retrieval, metadata, source coverage, download/read helpers.
- `paper-search` CLI: fallback when MCP is unavailable.
- `grok-search-rs`: optional supplemental recall through an OpenAI-compatible/Grok runtime; it does not replace `paper-search-mcp`.
- MinerU: PDF to Markdown/images/manifest parser for source bundles.
- EasyScholar: optional metric enrichment; failure is a soft warning.
- Zotero: optional record-only sidecar unless the user explicitly enables external sync.

## Healthy Outcome

A healthy Paper Source setup can:

- load the installed plugin and skill metadata;
- run `doctor --json` and `config-status --json`;
- identify whether a target vault is initialized;
- distinguish profile config from user runtime tooling;
- run discovery with available providers or explain provider gaps;
- stop safely before human approval, Paper Wiki final writing, and record updates.

