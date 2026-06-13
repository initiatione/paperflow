# Reset Repair

Use for destructive wiki reset, vault repair, config recovery, or misdelete recovery. Always load `references/reset-recovery.md` before reset, `--no-backup`, config reset, or misdelete recovery.

## Reset Protocol

Before and after destructive actions, report non-secret config state:

```powershell
python scripts\orchestrator.py config-status --vault <vault> --json --include-values --include-runtime
```

Reset is destructive. Do not reset from one sentence. First inventory the vault, run `config-status`, explain moved/removed/preserved paths, preview `wiki-reset --vault <vault> --preview --json`, and propose backup outside the active vault, for example `<vault-parent>\paper-research-wiki-reset-backups\<timestamp>`. Do not print secrets or delete config unless the separate config reset phrase is provided.

Require exact second confirmation `确认重置 Paper Source wiki`, then run:

```powershell
python scripts\orchestrator.py wiki-reset --vault <vault> --preview --json
python scripts\orchestrator.py wiki-reset --vault <vault> --confirmed-by "确认重置 Paper Source wiki" --json
python scripts\orchestrator.py wiki-reset --vault <vault> --confirmed-by "确认重置 Paper Source wiki" --no-backup --json
```

If backup is explicitly declined, `--no-backup` is allowed only for wiki content and still preserves config. Treat `不需要备份` as "do not back up wiki content"; it does not authorize config deletion.

Wiki structure reset and Paper Source config reset are separate operations. To reset config too, require `确认同时重置 Paper Source config`; do not infer config reset from `reset wiki`, `clean everything`, `no backup`, or `重新初始化`.

```powershell
python scripts\orchestrator.py wiki-reset --vault <vault> --confirmed-by "确认重置 Paper Source wiki" --reset-config-confirmed-by "确认同时重置 Paper Source config" --json
```

After reset, initialize, rerun `config-status`, and stop if config unexpectedly needs onboarding.

## Repair And Recovery

Use for accidental deletion, mistaken reset, missing config after preserve reset, or wording such as `误删`, `误操作`, `配置没了`, or `为什么要重新初始化 config`.

```powershell
python scripts\orchestrator.py wiki-repair --vault <vault> --json
python scripts\orchestrator.py config-recover --vault <vault> --json
python scripts\orchestrator.py config-restore --vault <vault> --from <backup-config-yaml> --confirmed-by "确认恢复 Paper Source config" --json
python scripts\orchestrator.py wiki-repair --vault <vault> --restore-from <backup-config-yaml> --confirmed-by "确认恢复 Paper Source config" --json
```

Never reset or delete outside the intended vault, while ingest/MinerU/promotion/wiki ingest is running, or without the exact second confirmation.
