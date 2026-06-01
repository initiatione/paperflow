---
name: wiki-setup
description: "Use when initializing, inspecting, repairing, or resetting an EPI paper wiki vault."
---

# EPI Wiki Setup

Use only for the target paper research wiki vault structure: initialize, inspect, repair, reset. Do not use for paper search, ingest, MinerU, Zotero, or final wiki writing. Load `references/reset-recovery.md` before reset, `--no-backup`, config reset, or Misdelete Recovery.

## Config Boundary

wiki structure reset and EPI config reset are separate operations. Default reset preserves config, even if the user says 不需要备份.

Preserve:

- `_epi\meta\epi-config.yaml`
- `_epi\meta\epi-config-state.json`
- `_epi\meta\epi-config-history\`
- `_epi\meta\config-history\`
- `%USERPROFILE%\.codex\plugins\paper-search\epi\runtime.json`

Before and after destructive actions, report non-secret config state only:

```powershell
python scripts\orchestrator.py config-status --vault <vault> --json --include-values --include-runtime
```

## Initialize

Initialization is idempotent:

```powershell
python scripts\init_paper_wiki.py --vault <vault>
```

Initialization must ensure the vault is a git repository. `init_paper_wiki.py` runs `git init` when `<vault>\.git` is missing, records `.git` in the created path list, and does not create a first commit. If `.git` already exists, preserve the existing repository.

Expected structure includes one EPI internal repository root `_epi`, wiki contract root `_meta`, wiki roots, `.obsidian`, `.git`, `index.md`, `log.md`, `hot.md`, and `.manifest.json`. New initialization must not create top-level `_raw`, `_staging`, `_runs`, `_quarantine`, or `_evolution`.

`_epi` must include navigation, manifest, and repository policy:

- `_epi\README.md`
- `_epi\manifest.json`
- `_epi\policies\retention.json`
- `_epi\raw\papers\`
- `_epi\staging\papers\`
- `_epi\staging\wiki-batches\pending\`
- `_epi\runs\`
- `_epi\quarantine\papers\`
- `_epi\evolution\`
- `_epi\meta\`

Obsidian graph views should ignore `_epi`; `_epi/raw/papers/<slug>/mineru/<slug>.md` remains source material, not a formal wiki page.

Initialization also seeds the vault contract files used by final wiki-ingest agents: `AGENTS.md`, `_meta\agent-operating-contract.md`, `_meta\schema.md`, `_meta\taxonomy.md`, and `_meta\directory-structure.md`. These defaults are source-first for paper research: final wiki pages must read `mineru\<slug>.md`, `mineru\paper.tex`, `mineru\images\*`, and `mineru\mineru-manifest.json`, then use reader/critic outputs as evidence aids.

For existing vaults with old top-level operational roots, migrate before or after initialization:

```powershell
python scripts\orchestrator.py epi-repository-migrate --vault <vault> --preview --json
python scripts\orchestrator.py epi-repository-migrate --vault <vault> --json
```

Then run cleanup preview:

```powershell
python scripts\orchestrator.py epi-repository-cleanup --vault <vault> --preview --json
```

## Reset

Reset is destructive. Do not reset from one sentence. Read `references/reset-recovery.md`; preview first:

```powershell
python scripts\orchestrator.py wiki-reset --vault <vault> --preview --json
python scripts\orchestrator.py wiki-reset --vault <vault> --confirmed-by "确认重置 EPI wiki" --json
```

Before reset, inventory the vault, run `config-status`, explain moved/removed/preserved paths, and propose backup outside the active vault such as `<vault-parent>\paper-research-wiki-reset-backups\<timestamp>`. Require exact second confirmation: `确认重置 EPI wiki`. Treat `不需要备份` as do not back up wiki content; it does not authorize config deletion.

If backup is explicitly declined:

```powershell
python scripts\orchestrator.py wiki-reset --vault <vault> --confirmed-by "确认重置 EPI wiki" --no-backup --json
```

To reset config too, require this separate phrase:

```text
确认同时重置 EPI config
```

Do not infer config reset from "reset wiki", "clean everything", "no backup", or "重新初始化".

```powershell
python scripts\orchestrator.py wiki-reset --vault <vault> --confirmed-by "确认重置 EPI wiki" --reset-config-confirmed-by "确认同时重置 EPI config" --json
```

After reset, initialize, rerun `config-status`, and stop if config unexpectedly needs onboarding. To reset or compact old operational roots, use `epi-repository-migrate` and `epi-repository-cleanup`; do not manually delete source paper artifacts.

## Misdelete Recovery

Use for accidental deletion, mistaken reset, missing config after preserve reset, or wording such as 误删, 误操作, 配置没了, 为什么要重新初始化 config. See `references/reset-recovery.md` for the recovery checklist.

```powershell
python scripts\orchestrator.py wiki-repair --vault <vault> --json
python scripts\orchestrator.py config-recover --vault <vault> --json
python scripts\orchestrator.py config-restore --vault <vault> --from <backup-config-yaml> --confirmed-by "确认恢复 EPI config" --json
python scripts\orchestrator.py wiki-repair --vault <vault> --restore-from <backup-config-yaml> --confirmed-by "确认恢复 EPI config" --json
```

Never reset/delete without the exact second confirmation, without preserving EPI config unless `确认同时重置 EPI config` was also provided, outside the intended vault, in unrelated paths, or while ingest/MinerU/promotion/wiki ingest is running.
