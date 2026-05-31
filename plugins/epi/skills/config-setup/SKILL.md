---
name: config-setup
description: "Use when EPI config is missing, viewed, initialized, or updated."
---

# EPI Config Setup

Single entrypoint for EPI config status, init, and updates. If config is missing, stop paper workflows and use this first. See `docs\config.md` for the full chat script and update flow.

## Read-Only Status

Use this for "show current config"; do not probe MCP, download papers, or call MinerU.

```powershell
python scripts\orchestrator.py config-status --vault <vault> --json --include-values --include-runtime
```

Only run `doctor` for dependency health, plugin diagnosis, MCP/CLI/MinerU availability, or setup failure.

## Hard Safety

- Before final confirmation, do not run `init-config`, `apply-config-update`, `dry-run`, MinerU, Zotero, promotion, or wiki writing.
- Required Chinese contract phrases: 最终确认前不得运行 `init-config`; 最终确认前不得运行 `apply-config-update`.
- Never print secrets; report token state as set/missing only.
- Runtime config: `%USERPROFILE%\.codex\plugins\paper-search\epi\runtime.json`.
- `runtime.json` stores command/env-file paths, not tokens: 不保存 token 明文. `MINERU_TOKEN` comes from env or `mineru.env`.

## Conversation Contract

- 一次只问一个问题.
- Do not use YAML field names as question titles.
- EPI 是通用论文插件: no field defaults.
- `docs\config.md` owns the onboarding script, `默认` escape hatch, technical preview, and update flow.
