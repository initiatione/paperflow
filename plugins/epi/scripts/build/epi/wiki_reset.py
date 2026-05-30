from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from epi.artifacts import utc_now, write_json_atomic
from epi.config import config_status
from epi.wiki_init import initialize_paper_wiki


WIKI_RESET_CONFIRMATION = "确认重置 EPI wiki"
CONFIG_RESET_CONFIRMATION = "确认同时重置 EPI config"

PROTECTED_META_NAMES = {
    "epi-config.yaml",
    "epi-config-state.json",
    "config-history",
    "epi-config-history",
}


def _unique_target(parent: Path, name: str) -> Path:
    candidate = parent / name
    counter = 1
    while candidate.exists():
        candidate = parent / f"{name}-{counter}"
        counter += 1
    return candidate


def _safe_timestamp() -> str:
    return utc_now().replace(":", "").replace("+", "Z").replace("-", "")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def _move_path(path: Path, backup_root: Path) -> Path:
    backup_root.mkdir(parents=True, exist_ok=True)
    target = _unique_target(backup_root, path.name)
    shutil.move(str(path), str(target))
    return target


def _reset_meta_dir(meta_dir: Path, backup_root: Path | None, *, preserve_config: bool) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    if not meta_dir.exists():
        return actions
    for child in sorted(meta_dir.iterdir(), key=lambda item: item.name):
        protected = preserve_config and child.name in PROTECTED_META_NAMES
        if protected:
            actions.append({"action": "preserve", "path": str(child)})
            continue
        if backup_root is None:
            _remove_path(child)
            actions.append({"action": "remove", "path": str(child)})
        else:
            moved_to = _move_path(child, backup_root / "_meta")
            actions.append({"action": "backup", "path": str(child), "backup_path": str(moved_to)})
    return actions


def reset_wiki_vault(
    vault_path: Path,
    *,
    confirmed_by: str,
    reset_config_confirmed_by: str | None = None,
    backup_root: Path | None = None,
    no_backup: bool = False,
) -> dict[str, Any]:
    if confirmed_by != WIKI_RESET_CONFIRMATION:
        raise ValueError(f"wiki reset requires confirmed_by='{WIKI_RESET_CONFIRMATION}'")
    preserve_config = reset_config_confirmed_by != CONFIG_RESET_CONFIRMATION
    vault_path = vault_path.resolve()
    if vault_path.parent == vault_path:
        raise ValueError("refusing to reset filesystem root")
    if not vault_path.exists():
        vault_path.mkdir(parents=True)
    if not vault_path.is_dir():
        raise ValueError(f"vault is not a directory: {vault_path}")

    if backup_root is None and not no_backup:
        backup_root = vault_path.parent / "paper-research-wiki-reset-backups" / _safe_timestamp()
    if backup_root is not None:
        backup_root = backup_root.resolve()
        if _is_relative_to(backup_root, vault_path):
            raise ValueError("backup_root must be outside the active vault")

    before_config = config_status(vault_path)
    actions: list[dict[str, Any]] = []
    for child in sorted(vault_path.iterdir(), key=lambda item: item.name):
        if child.name == "_meta":
            actions.extend(_reset_meta_dir(child, backup_root, preserve_config=preserve_config))
            continue
        if backup_root is None:
            _remove_path(child)
            actions.append({"action": "remove", "path": str(child)})
        else:
            moved_to = _move_path(child, backup_root)
            actions.append({"action": "backup", "path": str(child), "backup_path": str(moved_to)})

    created = initialize_paper_wiki(vault_path)
    after_config = config_status(vault_path)
    manifest_dir = vault_path / "_meta" / "wiki-reset"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / f"{_safe_timestamp()}-wiki-reset.json"
    result = {
        "status": "reset",
        "vault_path": str(vault_path),
        "backup_root": str(backup_root) if backup_root else None,
        "no_backup": no_backup,
        "preserved_config": preserve_config and after_config["configured"],
        "reset_config": not preserve_config,
        "before_config": before_config,
        "after_config": after_config,
        "created": created,
        "actions": actions,
        "manifest_path": str(manifest_path),
    }
    write_json_atomic(manifest_path, result)
    return result
