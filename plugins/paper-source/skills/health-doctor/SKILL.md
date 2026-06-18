---
name: health-doctor
description: >
  Use when diagnosing, configuring, validating, or repairing Paper Source / PS, Paper Wiki / PW, PaperFlow, MCP servers, user profile/config, runtime.json/env files, paper-search, grok-search-rs, OpenAI-compatible or Grok gateways, MinerU, EasyScholar, Zotero, vault bootstrap, formal-page contracts, network/proxy/Cloudflare 403 symptoms, or setup failures such as "配置/检查/修复 Paper Source", "Paper Wiki 不能用", "MCP 调不通", "插件不能调用".
---

# PaperFlow Health Doctor

Use this as the top-level triage entry for Paper Source + Paper Wiki health. Start read-only, identify which layer is unhealthy, then route to the focused Paper Source or Paper Wiki skill that owns the repair.

## First Pass

Run the built-in doctor before custom probing:

```powershell
python scripts\orchestrator.py doctor --vault <vault> --json
python scripts\orchestrator.py config-status --vault <vault> --json --include-values --include-runtime
```

Never print secrets. Report tokens, API keys, passwords, auth headers, cookies, and env-file values only as set/missing/redacted. Do not encode private endpoints, local proxy rules, subscription names, cache paths, or local tokens into the skill.

## Reference Routing

Load only the reference needed for the failing layer:

- `references/paper-source-health.md` for Paper Source config, runtime.json, provider readiness, MinerU, EasyScholar, Zotero, and installed-vs-source validation.
- `references/paper-wiki-health.md` for vault bootstrap, Paper Wiki availability, formal-page contracts, QMD boundaries, and source-first handoff health.
- `references/mcp-runtime-health.md` for Codex MCP registration, plugin `.mcp.json`, stdio handshake, `paper-search-mcp`, and `grok-search-rs`.
- `references/network-gateway-health.md` for OpenAI-compatible/Grok upstreams, Cloudflare 403/challenge, auth, proxy, DNS, TLS, and non-JSON provider failures.
- `references/repair-playbooks.md` before any write, reset, restore, config update, dependency install, or irreversible cleanup.

## Route To Owner

- Missing or stale profile/runtime config -> `config-setup`.
- Vault initialization, reset, graph visibility, or `_paper_source` structure -> `wiki-setup`.
- Discovery result quality, provider coverage, Grok contribution, or recommendation output -> `paper-discovery`.
- PDF acquisition, MinerU parse, source bundle, approval report, or wiki handoff -> `paper-ingest` or `mineru-paper-parser`.
- Final page provenance, source links, claim support, or record readiness -> `wiki-provenance`.
- Run/repository cleanup -> `run-lifecycle`; Zotero sidecars -> `zotero-sync`; plugin behavior changes -> `skill-aware-evolve`.
- Formal page writing, wiki ask/deposit/check/update/relink -> Paper Wiki `$paper-research-wiki`, not this skill.

## Safe Probes

Use bundled probes when the built-in doctor is not enough:

```powershell
python skills\health-doctor\scripts\redacted_env_status.py --env-file <file>
python skills\health-doctor\scripts\mcp_stdio_probe.py --command <cmd> --arg <arg1> --arg <arg2>
python skills\health-doctor\scripts\openai_compatible_probe.py --base-url <url> --api-key-env OPENAI_COMPATIBLE_API_KEY
```

These probes are diagnostic helpers, not the source of truth. Prefer Paper Source `doctor --json` whenever it already reports the same layer.

## Repair Boundary

Ask for explicit confirmation before running `init-config`, `apply-config-update`, `config-restore`, `wiki-reset`, `wiki-repair --restore-from`, `parse-paper`, `prepare-ranked`, `discover-to-handoff`, `record-human-approval`, `wiki-ingest-trigger`, `record-wiki-ingest`, Zotero sync with external effects, or any dependency install/upgrade. For suspected installed-cache staleness, report source-checkout validation separately from marketplace refresh, reinstall, and installed-cache verification.
