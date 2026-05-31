# Reset And Recovery

Load this only when reset, `--no-backup`, config reset, or recovery is in scope.

## Reset Checklist

1. Inventory the vault root and important EPI directories.
2. Run `config-status`.
3. Explain moved, removed, and preserved paths.
4. Propose backup outside the active vault, for example `<vault-parent>\paper-research-wiki-reset-backups\<timestamp>`.
5. Require exact second confirmation: `确认重置 EPI wiki`.
6. Treat `不需要备份` as do not back up wiki content; it never authorizes config deletion.
7. Reset while preserving config, initialize, rerun `config-status`, and stop if onboarding is unexpectedly required.

Only reset config when the user separately provides `确认同时重置 EPI config`; pass it through `--reset-config-confirmed-by`.

## Misdelete Recovery

For 误删, 误操作, missing config, or mistaken reset:

1. Stop search, ingest, MinerU, staging, promotion, and wiki writing.
2. Explain the likely boundary error.
3. Actively ask whether the user wants help restoring important settings from backups or history.
4. Search safe sources first: reset backups, `_meta\epi-config-history\`, `_meta\config-history\`, plugin git history, non-secret Codex logs, and `%USERPROFILE%\.codex\plugins\paper-search\epi\runtime.json`.
5. Show path, timestamp, and non-secret summary before restore.
6. If no backup exists, use `config-setup` and state unrecovered settings.

```powershell
python scripts\orchestrator.py wiki-repair --vault <vault> --json
python scripts\orchestrator.py config-recover --vault <vault> --json
python scripts\orchestrator.py config-restore --vault <vault> --from <backup-config-yaml> --confirmed-by "确认恢复 EPI config" --json
python scripts\orchestrator.py wiki-repair --vault <vault> --restore-from <backup-config-yaml> --confirmed-by "确认恢复 EPI config" --json
```
