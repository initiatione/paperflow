from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from epi.artifacts import epi_meta_root, legacy_meta_root, utc_now, write_json_atomic
from epi.config import config_status
from epi.config_protection import CONFIG_RESET_CONFIRMATION, PROTECTED_META_NAMES, WIKI_RESET_CONFIRMATION
from epi.wiki_init import initialize_paper_wiki


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


def _action_record(action: str, path: Path, backup_path: Path | None = None) -> dict[str, Any]:
    record = {"action": action, "path": str(path)}
    if backup_path is not None:
        record["backup_path"] = str(backup_path)
    return record


def _reset_meta_dir(
    meta_dir: Path,
    backup_root: Path | None,
    *,
    preserve_config: bool,
    backup_relative_root: Path | None = None,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    if not meta_dir.exists():
        return actions
    for child in sorted(meta_dir.iterdir(), key=lambda item: item.name):
        protected = preserve_config and child.name in PROTECTED_META_NAMES
        if protected:
            actions.append(_action_record("preserve", child))
            continue
        if backup_root is None:
            _remove_path(child)
            actions.append(_action_record("remove", child))
        else:
            relative_root = backup_relative_root or Path("_meta")
            moved_to = _move_path(child, backup_root / relative_root)
            actions.append(_action_record("backup", child, moved_to))
    return actions


def preview_wiki_reset(
    vault_path: Path,
    *,
    reset_config_confirmed_by: str | None = None,
    backup_root: Path | None = None,
    no_backup: bool = False,
) -> dict[str, Any]:
    preserve_config = reset_config_confirmed_by != CONFIG_RESET_CONFIRMATION
    vault_path = vault_path.resolve()
    effective_backup_root = None
    if backup_root is not None:
        effective_backup_root = backup_root.resolve()
    elif not no_backup:
        effective_backup_root = vault_path.parent / "paper-research-wiki-reset-backups" / "<timestamp>"
    actions: list[dict[str, Any]] = []
    if vault_path.exists() and vault_path.is_dir():
        for child in sorted(vault_path.iterdir(), key=lambda item: item.name):
            if child.name == "_epi":
                meta_dir = epi_meta_root(vault_path)
                if meta_dir.exists():
                    for meta_child in sorted(meta_dir.iterdir(), key=lambda item: item.name):
                        if preserve_config and meta_child.name in PROTECTED_META_NAMES:
                            actions.append(_action_record("would_preserve", meta_child))
                        elif effective_backup_root is None:
                            actions.append(_action_record("would_remove", meta_child))
                        else:
                            actions.append(
                                _action_record(
                                    "would_backup",
                                    meta_child,
                                    effective_backup_root / "_epi" / "meta" / meta_child.name,
                                )
                            )
                for epi_child in sorted(child.iterdir(), key=lambda item: item.name):
                    if epi_child.name == "meta":
                        continue
                    if effective_backup_root is None:
                        actions.append(_action_record("would_remove", epi_child))
                    else:
                        actions.append(_action_record("would_backup", epi_child, effective_backup_root / "_epi" / epi_child.name))
                continue
            if child.name == "_meta":
                for meta_child in sorted(child.iterdir(), key=lambda item: item.name) if child.exists() else []:
                    if preserve_config and meta_child.name in PROTECTED_META_NAMES:
                        actions.append(_action_record("would_preserve", meta_child))
                    elif effective_backup_root is None:
                        actions.append(_action_record("would_remove", meta_child))
                    else:
                        actions.append(_action_record("would_backup", meta_child, effective_backup_root / "_meta" / meta_child.name))
                continue
            if effective_backup_root is None:
                actions.append(_action_record("would_remove", child))
            else:
                actions.append(_action_record("would_backup", child, effective_backup_root / child.name))
    return {
        "status": "preview",
        "vault_path": str(vault_path),
        "backup_root": str(effective_backup_root) if effective_backup_root else None,
        "no_backup": no_backup,
        "preserve_config": preserve_config,
        "config_status": config_status(vault_path),
        "actions": actions,
    }


def reset_wiki_vault(
    vault_path: Path,
    *,
    confirmed_by: str | None,
    reset_config_confirmed_by: str | None = None,
    backup_root: Path | None = None,
    no_backup: bool = False,
    preview: bool = False,
) -> dict[str, Any]:
    if preview:
        return preview_wiki_reset(
            vault_path,
            reset_config_confirmed_by=reset_config_confirmed_by,
            backup_root=backup_root,
            no_backup=no_backup,
        )
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
        if child.name in {"_meta", "_epi"}:
            if child.name == "_epi":
                meta_dir = epi_meta_root(vault_path)
                if meta_dir.exists():
                    actions.extend(
                        _reset_meta_dir(
                            meta_dir,
                            backup_root,
                            preserve_config=preserve_config,
                            backup_relative_root=Path("_epi") / "meta",
                        )
                    )
                for epi_child in sorted(child.iterdir(), key=lambda item: item.name):
                    if epi_child.name == "meta":
                        continue
                    if backup_root is None:
                        _remove_path(epi_child)
                        actions.append(_action_record("remove", epi_child))
                    else:
                        moved_to = _move_path(epi_child, backup_root / "_epi")
                        actions.append(_action_record("backup", epi_child, moved_to))
                continue
            actions.extend(_reset_meta_dir(child, backup_root, preserve_config=preserve_config))
            continue
        if backup_root is None:
            _remove_path(child)
            actions.append(_action_record("remove", child))
        else:
            moved_to = _move_path(child, backup_root)
            actions.append(_action_record("backup", child, moved_to))

    created = initialize_paper_wiki(vault_path)
    after_config = config_status(vault_path)
    manifest_dir = epi_meta_root(vault_path) / "wiki-reset"
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
