# Repair Playbooks

Use this reference before any action that writes config, changes runtime files, repairs a vault, resets state, installs dependencies, runs heavy parse/discovery, or touches Paper Wiki records.

## Safety Rules

- Start with read-only diagnosis.
- Preserve user changes and user vault content.
- Ask for explicit confirmation before writes, resets, restores, installs, upgrades, MinerU runs, discovery-to-handoff, approval/trigger, or record updates.
- Do not print secrets or copy env-file contents into chat, docs, reports, or artifacts.
- Keep source checkout validation separate from installed-cache validation.

## Config Missing Or Corrupt

1. Run `config-status --json --include-values --include-runtime`.
2. If config is missing, route to `config-setup`; do not run paper workflows.
3. If config history exists, inspect `config-recover --json`.
4. Restore only after the user confirms the exact config backup and restore command.

## Runtime Path Invalid

1. Use `doctor --json` and check runtime path policy.
2. Prefer user-level runtime directories and stable globally installed commands.
3. Do not point runtime.json at a development checkout, versioned installed cache, vault-internal file, temp file, or project-local secret file unless the user explicitly accepts the portability cost.
4. Store secrets in env files or process env; runtime.json stores only paths and command shape.

## MCP Not Callable

1. Confirm whether Codex is loading source checkout or installed plugin cache.
2. Check user-level static MCP config for entries that shadow plugin self-registration.
3. Validate outer launcher `cwd`, command, and placeholder expansion.
4. Validate inner server command with the native tool or `mcp_stdio_probe.py`.
5. If source checkout changed, refresh marketplace/reinstall and start a new Codex thread before claiming live runtime success.

## Cloudflare 403 Or Non-JSON Gateway

1. Run the OpenAI-compatible probe against `/v1/models`.
2. Classify the response: Cloudflare challenge, auth/forbidden, non-JSON, timeout, TLS, or upstream error.
3. For Cloudflare challenge, fix the upstream API route or network policy outside Paper Source.
4. For auth/forbidden, check key, model entitlement, account, IP allowlist, and route.
5. For DNS/proxy/TLS, adjust the user's runtime network environment, not plugin defaults.

## Vault Missing Or Damaged

1. Run `doctor --vault <vault> --json`.
2. Use `wiki-setup` for initialization or repair.
3. Before reset, load the reset/repair workflow and require the exact confirmation phrase.
4. Preserve Paper Source config and config history unless the user separately confirms config reset.

## Source Bundle Or MinerU Failure

1. Run `paper-gate --slug <slug> --vault <vault>`.
2. Distinguish missing PDF, manual-download-required, identity mismatch, MinerU missing, parse timeout, missing Markdown, and source bundle incomplete.
3. Use `mineru-paper-parser` for low-level parse/asset issues.
4. Do not proceed to Paper Wiki formal writing until the source bundle and handoff are healthy.

## Paper Wiki Contract Failure

1. Route final-page fixes to Paper Wiki `$paper-research-wiki`.
2. Use Paper Source `wiki-provenance` only for source link/provenance/record readiness checks.
3. After Paper Wiki repairs pages and `final-source-review.json`, use Paper Source `record-wiki-ingest` only when the record gate is ready.

