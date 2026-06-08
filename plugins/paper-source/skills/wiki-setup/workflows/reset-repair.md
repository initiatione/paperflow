# Reset Repair

Use this workflow for destructive wiki reset, vault repair, config recovery, or misdelete recovery.

Always load `references/reset-recovery.md` before reset, `--no-backup`, config reset, or misdelete recovery.

## Inspect Config State

Before and after destructive actions, report non-secret config state:

```powershell
python scripts\orchestrator.py config-status --vault <vault> --json --include-values --include-runtime
```

Do not print secrets or delete config unless the separate config reset phrase is provided.

## Reset Preview

Reset is destructive. Do not reset from one sentence. Preview first:

```powershell
python scripts\orchestrator.py wiki-reset --vault <vault> --preview --json
```

Before reset, inventory the vault, run `config-status`, explain moved/removed/preserved paths, and propose backup outside the active vault, such as:

```text
<vault-parent>\paper-research-wiki-reset-backups\<timestamp>
```

## Confirm Wiki Reset

Require this exact second confirmation:

```text
确认重置 EPI wiki
```

Then run:

```powershell
python scripts\orchestrator.py wiki-reset --vault <vault> --confirmed-by "确认重置 EPI wiki" --json
```

If backup is explicitly declined, this is allowed only for wiki content and still preserves config:

```powershell
python scripts\orchestrator.py wiki-reset --vault <vault> --confirmed-by "确认重置 EPI wiki" --no-backup --json
```

Treat `不需要备份` as "do not back up wiki content"; it does not authorize config deletion.

## Confirm Config Reset

To reset config too, require this separate phrase:

```text
确认同时重置 EPI config
```

Do not infer config reset from `reset wiki`, `clean everything`, `no backup`, or `重新初始化`.

```powershell
python scripts\orchestrator.py wiki-reset --vault <vault> --confirmed-by "确认重置 EPI wiki" --reset-config-confirmed-by "确认同时重置 EPI config" --json
```

After reset, initialize, rerun `config-status`, and stop if config unexpectedly needs onboarding.

## Repair And Recovery

Use for accidental deletion, mistaken reset, missing config after preserve reset, or wording such as `误删`, `误操作`, `配置没了`, or `为什么要重新初始化 config`.

```powershell
python scripts\orchestrator.py wiki-repair --vault <vault> --json
python scripts\orchestrator.py config-recover --vault <vault> --json
python scripts\orchestrator.py config-restore --vault <vault> --from <backup-config-yaml> --confirmed-by "确认恢复 EPI config" --json
python scripts\orchestrator.py wiki-repair --vault <vault> --restore-from <backup-config-yaml> --confirmed-by "确认恢复 EPI config" --json
```

Never reset or delete outside the intended vault, while ingest/MinerU/promotion/wiki ingest is running, or without the exact second confirmation.
