---
name: wiki-setup
description: "Use when the user wants to initialize, create, inspect, repair, or reset the EPI paper research wiki vault structure. Reset is destructive, preserves EPI config by default, and must require a second explicit confirmation before any deletion or move."
---

# EPI Wiki Setup

Use this skill only for the target paper research wiki vault structure, not for paper search, paper ingest, MinerU, Zotero, or final wiki writing.

## Config Boundary

Treat them separately: wiki structure reset and EPI config reset are separate operations. They need separate confirmations.

The default reset preserves EPI configuration, even when the user says they do not need a backup. Preserve these vault-local paths when present:

- `_meta\epi-config.yaml`
- `_meta\epi-config-state.json`
- `_meta\epi-config-history\`
- `_meta\config-history\`

Also treat the user-level runtime config as outside the wiki vault and never delete it from this skill:

- `%USERPROFILE%\.codex\plugins\paper-search\epi\runtime.json`

Before and after any reset, run config status and report only non-secret state:

```powershell
python scripts\orchestrator.py config-status --vault <vault> --json --include-values --include-runtime
```

Report whether `_meta\epi-config.yaml` exists, whether onboarding is needed, and whether `MINERU_TOKEN` is set or missing. Do not print token values or other secrets.

## Initialize

Initialization is idempotent. It creates missing directories and seed files without deleting existing content:

```powershell
python scripts\init_paper_wiki.py --vault <vault>
```

Expected structure includes `_raw\papers`, `_staging\papers`, `_quarantine\papers`, `_runs`, `_evolution`, `_meta`, `references`, `concepts`, `synthesis`, `entities`, `skills`, `projects`, `journal`, `.obsidian`, `index.md`, `log.md`, `hot.md`, and `.manifest.json`.

After initialization, summarize the created paths and tell the user that existing files were preserved.

## Reset

Reset is destructive. Do not reset immediately from a single user sentence.

Before reset:

1. Run a read-only inventory of the vault root and important EPI directories.
2. Run `config-status --vault <vault> --json --include-values --include-runtime` and record whether config exists before the reset.
3. Explain exactly what will be moved, removed, or preserved. Explicitly list the config preservation behavior from **Config Boundary**.
4. Create or propose a backup outside the active vault, such as `<vault-parent>\paper-research-wiki-reset-backups\<timestamp>`.
5. Ask for a second explicit confirmation using the exact phrase: `确认重置 EPI wiki`.
6. If the user says `不需要备份`, interpret that as "do not back up wiki content"; it does not authorize deleting EPI config.
7. Only after that confirmation, move or remove reset targets while preserving config paths, then run initialization.

To also delete or reset EPI config, require a separate explicit confirmation phrase in the same reset discussion:

```text
确认同时重置 EPI config
```

Do not infer config reset from "reset wiki", "clean everything", "no backup", or "重新初始化". Without that extra phrase, protect config files and runtime.json.

After reset:

1. Run initialization.
2. Run `config-status --vault <vault> --json --include-values --include-runtime` again.
3. Report whether config was preserved or now needs onboarding.
4. If config is unexpectedly missing, stop and ask whether to restore or reinitialize config; do not continue into paper discovery, ingest, MinerU, or wiki-writing workflows.

## Misdelete Recovery

If you detect an accidental deletion, mistaken reset, missing config after a supposed preserve reset, or any user report like "误删", "误操作", "配置没了", or "为什么要重新初始化 config":

1. Stop the current workflow before paper search, paper ingest, MinerU, staging, or wiki writing.
2. Explain the likely boundary error in plain language: wiki content cleanup may have removed vault-local config, while user-level runtime.json may still exist.
3. Actively ask whether the user wants help restoring important settings from backups or history.
4. Search safe recovery sources before asking the user to re-enter settings:
   - proposed reset backup roots such as `<vault-parent>\paper-research-wiki-reset-backups\`
   - `_meta\epi-config-history\` or `_meta\config-history\` if preserved
   - recent git history in `<plugin-repo>` for skill or template defaults
   - Codex logs only for non-secret config state; never print secrets
   - `%USERPROFILE%\.codex\plugins\paper-search\epi\runtime.json` for runtime command paths and env-file location
5. If a plausible backup config is found, show its path, timestamp, and non-secret summary, then ask for confirmation before restoring it.
6. If no backup exists, help reinitialize config with the `config-setup` skill and explicitly say which settings could not be recovered.

Never reset or delete:

- without the exact second confirmation
- without preserving EPI config unless `确认同时重置 EPI config` was also provided
- if the resolved target path is not the intended vault
- by touching unrelated repositories or parent directories
- while paper ingest, MinerU parse, promotion, or wiki ingest is running

When unsure, stop after inventory and backup proposal.
