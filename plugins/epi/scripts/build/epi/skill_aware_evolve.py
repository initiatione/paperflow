from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from epi.artifacts import utc_now, write_json_atomic, write_text_atomic


WHITELISTED_TEMPLATE_ASSETS = {
    "templates/ranking.example.yaml",
    "templates/critic-checklist.example.yaml",
}


def _normalize_asset_key(target_asset: str) -> str:
    return target_asset.replace("\\", "/")


def _parse_yaml_scalar(raw: str) -> Any:
    if raw.startswith('"') and raw.endswith('"'):
        return json.loads(raw)
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def _parse_simple_yaml_mapping(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()
        key, separator, value = stripped.partition(":")
        if not separator:
            raise ValueError(f"unsupported yaml line: {raw_line}")
        while indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if value.strip():
            parent[key] = _parse_yaml_scalar(value.strip())
            continue
        node: dict[str, Any] = {}
        parent[key] = node
        stack.append((indent, node))
    return root


def _dump_yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False) if any(ch.isspace() for ch in str(value)) or ":" in str(value) else str(value)


def _dump_simple_yaml_mapping(payload: dict[str, Any], *, indent: int = 0) -> list[str]:
    lines: list[str] = []
    prefix = " " * indent
    for key, value in payload.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.extend(_dump_simple_yaml_mapping(value, indent=indent + 2))
        else:
            lines.append(f"{prefix}{key}: {_dump_yaml_scalar(value)}")
    return lines


def _deep_merge_mapping(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge_mapping(base[key], value)
            continue
        base[key] = value
    return base


def _apply_template_change(asset_path: Path, proposed_change: dict[str, Any]) -> None:
    current = _parse_simple_yaml_mapping(asset_path.read_text(encoding="utf-8"))
    merged = _deep_merge_mapping(current, proposed_change)
    content = "\n".join(_dump_simple_yaml_mapping(merged)) + "\n"
    write_text_atomic(asset_path, content)


def propose_evolution(
    vault_path: Path,
    *,
    reflection_type: str,
    target_asset: str,
    rationale: str,
    proposed_change: dict[str, Any],
    evidence: list[str],
) -> dict:
    proposal_id = f"evo-{uuid.uuid4().hex[:12]}"
    proposal = {
        "id": proposal_id,
        "status": "proposed",
        "created_at": utc_now(),
        "reflection_type": reflection_type,
        "target_asset": target_asset,
        "rationale": rationale,
        "proposed_change": proposed_change,
        "evidence": evidence,
        "activation_requires_human_approval": True,
        "rollback_instructions": "Move active record to archive and restore the previous controlled asset version.",
    }
    path = vault_path.resolve() / "_evolution" / "proposals" / f"{proposal_id}.json"
    write_json_atomic(path, proposal)
    return proposal


def activate_evolution(vault_path: Path, proposal_id: str, *, approved: bool) -> dict:
    if not approved:
        raise PermissionError("human approval is required before activating evolution proposals")
    vault_path = vault_path.resolve()
    proposal_path = vault_path / "_evolution" / "proposals" / f"{proposal_id}.json"
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    target_asset = proposal["target_asset"]
    normalized_target_asset = _normalize_asset_key(target_asset)
    activated = {
        **proposal,
        "status": "active",
        "activated_at": utc_now(),
        "code_modified": False,
    }
    if normalized_target_asset not in WHITELISTED_TEMPLATE_ASSETS:
        activated["asset_application"] = {
            "status": "record_only",
            "target_asset": target_asset,
            "reason": "target_asset_not_whitelisted",
            "backup_created": False,
        }
    else:
        asset_path = vault_path / Path(target_asset)
        backup_dir = vault_path / "_evolution" / "backups" / proposal_id
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / asset_path.name
        shutil.copyfile(asset_path, backup_path)
        _apply_template_change(asset_path, proposal["proposed_change"])
        activated["asset_application"] = {
            "status": "applied",
            "target_asset": target_asset,
            "asset_path": str(asset_path),
            "backup_created": True,
            "backup_path": str(backup_path),
        }
        activated["rollback"] = {
            "target_asset": target_asset,
            "backup_path": str(backup_path),
            "restore_action": "restore_file_copy",
        }
    active_path = vault_path / "_evolution" / "active" / f"{proposal_id}.json"
    write_json_atomic(active_path, activated)
    archive_dir = vault_path / "_evolution" / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(proposal_path, archive_dir / f"{proposal_id}.proposed.json")
    return activated
