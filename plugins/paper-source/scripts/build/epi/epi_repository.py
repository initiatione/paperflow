from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from epi.artifacts import (
    epi_meta_root,
    epi_root,
    evolution_root,
    policies_root,
    quarantine_root,
    raw_papers_root,
    runs_root,
    staging_papers_root,
    utc_now,
    wiki_batch_pending_root,
    write_json_atomic,
    write_text_atomic,
)


DEFAULT_RETENTION_POLICY: dict[str, Any] = {
    "schema_version": "epi-retention-policy-v1",
    "auto_cleanup_enabled": True,
    "max_total_files": 3000,
    "max_total_bytes": 1 * 1024 * 1024 * 1024,
    "runs": {
        "keep_latest": 15,
        "keep_per_workflow": 2,
    },
    "staging": {
        "keep_pending_wiki_batches": 8,
    },
    "lifecycle": {
        "enforce_even_when_under_budget": True,
        "meta_manifests": {
            "run-lifecycle": {"keep_latest": 20},
            "raw-cleanup": {"keep_latest": 30},
            "repository-maintenance": {"keep_latest": 20},
            "migrations": {"keep_latest": 20},
            "wiki-reset": {"keep_latest": 10},
        },
        "formal_page_snapshots": {"keep_latest": 3},
        "temporary_files": {
            "tmp-manual-pdfs": {"keep_latest": 5},
        },
    },
    "protected": [
        "raw",
        "meta/epi-config.yaml",
        "meta/epi-config-state.json",
        "meta/config-history",
        "README.md",
        "manifest.json",
        "policies/retention.json",
    ],
    "notes": [
        "Default cleanup is conservative: raw paper sources and MinerU artifacts are not deleted.",
        "Cleanup always enforces lifecycle caps for transient runs, maintenance manifests, snapshots, and temporary manual PDFs.",
    ],
}


EPI_REPOSITORY_README = """# EPI Internal Repository

This `_epi` folder is the internal EPI workspace for source-first paper evidence, handoff, configuration, and maintenance records. It is not part of the formal Obsidian graph.

## Core Structure

- `_epi/raw/<slug>/`: durable source paper bundle. Keep `paper.pdf`, `metadata.json`, MinerU Markdown/TeX/images/manifest, and acquisition/parse records here.
- `_epi/staging/papers/<slug>/`: per-paper evidence handoff for PRW. These files are not formal wiki pages.
- `_epi/staging/wiki-batches/pending/wiki-batch-ingest-brief.json`: batch handoff for wiki skill deposition.
- `_epi/meta/`: EPI config, config history, formal-page snapshots, and bounded maintenance records.
- `_epi/policies/retention.json`: cleanup policy.

## On-Demand Structure

The following directories are created only when a workflow needs them, not as empty bootstrap shells:

- `_epi/runs/`: transient run reports, dashboards, query plans, and execution state.
- `_epi/cache/`: regenerable provider cache.
- `_epi/tmp/` and `_epi/tmp-manual-pdfs/`: temporary acquisition and manual PDF recovery staging.
- `_epi/quarantine/`: failed or isolated paper artifacts.
- `_epi/evolution/`: controlled skill/profile/template evolution proposals when vault-local evidence must be attached.

## Agent Contract

1. Start here, then read `AGENTS.md` and root `_meta/*` before final wiki writing.
2. Use EPI reader/critic/staging outputs as navigation and quality signals only.
3. Final wiki pages must be distilled from original paper artifacts, formulas, figures, images, and batch-level comparison.
4. Never promote `_epi/staging`, `_epi/runs`, or raw source Markdown as formal wiki pages.
5. New EPI writes must stay under `_epi`; root `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/` are wiki-skill-owned.
"""


REQUIRED_EPI_DIRS = [
    "raw",
    "staging/papers",
    "staging/wiki-batches/pending",
    "meta/config-history",
    "meta/formal-page-snapshots",
    "policies",
]


LEGACY_INTERNAL_ROOTS = {
    "_raw": "raw",
    "_staging": "staging",
    "_runs": "runs",
    "_quarantine": "quarantine",
    "_evolution": "evolution",
}


def ensure_epi_repository(vault_path: Path) -> list[str]:
    vault_path = vault_path.resolve()
    created: list[str] = []
    root = epi_root(vault_path)
    if not root.exists():
        created.append("_epi")
    root.mkdir(parents=True, exist_ok=True)
    for relative_dir in REQUIRED_EPI_DIRS:
        path = root / relative_dir
        if not path.exists():
            created.append(f"_epi/{relative_dir}")
        path.mkdir(parents=True, exist_ok=True)

    files = {
        "README.md": EPI_REPOSITORY_README,
        "policies/retention.json": DEFAULT_RETENTION_POLICY,
    }
    for relative_file, payload in files.items():
        path = root / relative_file
        if path.exists():
            continue
        if isinstance(payload, str):
            write_text_atomic(path, payload)
        else:
            write_json_atomic(path, payload)
        created.append(f"_epi/{relative_file}")
    refresh_epi_manifest(vault_path)
    return created


def _dir_stats(path: Path) -> dict[str, int]:
    file_count = 0
    total_bytes = 0
    if not path.exists():
        return {"file_count": 0, "total_bytes": 0}
    for item in path.rglob("*"):
        if item.is_file():
            file_count += 1
            try:
                total_bytes += item.stat().st_size
            except OSError:
                pass
    return {"file_count": file_count, "total_bytes": total_bytes}


def refresh_epi_manifest(vault_path: Path) -> dict[str, Any]:
    vault_path = vault_path.resolve()
    root = epi_root(vault_path)
    manifest = {
        "schema_version": "epi-internal-repository-manifest-v1",
        "updated_at": utc_now(),
        "root": "_epi",
        "write_scope": "EPI writes only under _epi; formal wiki pages are wiki-skill-owned.",
        "graph_visibility": "ignore _epi in Obsidian graph; use _epi/README.md for agent navigation.",
        "core_sections": {
            "raw": "raw/<slug>/ source PDFs, MinerU markdown, TeX, images, manifests",
            "staging": "staging/papers/<slug>/ internal evidence and wiki handoff",
            "wiki_batches": "staging/wiki-batches/pending/ batch handoff for wiki skill",
            "meta": "meta/ config, formal-page snapshots, bounded maintenance records",
            "policies": "policies/ retention and cleanup policy",
        },
        "on_demand_sections": {
            "runs": "runs/ workflow reports, dashboards, query records, transient state; not precreated",
            "cache": "cache/ regenerable provider cache; not precreated",
            "tmp": "tmp/ temporary acquisition staging; not precreated",
            "tmp_manual_pdfs": "tmp-manual-pdfs/ manual PDF recovery staging; not precreated",
            "quarantine": "quarantine/ failed or isolated artifacts; not precreated",
            "evolution": "evolution/ controlled EPI profile/template/skill changes; not precreated",
        },
        "stats": {
            "raw": _dir_stats(raw_papers_root(vault_path)),
            "staging": _dir_stats(staging_papers_root(vault_path).parent),
            "runs": _dir_stats(runs_root(vault_path)),
            "cache": _dir_stats(epi_root(vault_path) / "cache"),
            "tmp": _dir_stats(epi_root(vault_path) / "tmp"),
            "tmp_manual_pdfs": _dir_stats(epi_root(vault_path) / "tmp-manual-pdfs"),
            "quarantine": _dir_stats(quarantine_root(vault_path)),
            "evolution": _dir_stats(evolution_root(vault_path)),
            "meta": _dir_stats(epi_meta_root(vault_path)),
        },
    }
    write_json_atomic(root / "manifest.json", manifest)
    return manifest


def inspect_epi_manifest(vault_path: Path) -> dict[str, Any]:
    vault_path = vault_path.resolve()
    return {
        "schema_version": "epi-internal-repository-manifest-v1",
        "updated_at": utc_now(),
        "root": "_epi",
        "write_scope": "EPI writes only under _epi; formal wiki pages are wiki-skill-owned.",
        "graph_visibility": "ignore _epi in Obsidian graph; use _epi/README.md for agent navigation.",
        "stats": {
            "raw": _dir_stats(raw_papers_root(vault_path)),
            "staging": _dir_stats(staging_papers_root(vault_path).parent),
            "runs": _dir_stats(runs_root(vault_path)),
            "cache": _dir_stats(epi_root(vault_path) / "cache"),
            "tmp": _dir_stats(epi_root(vault_path) / "tmp"),
            "tmp_manual_pdfs": _dir_stats(epi_root(vault_path) / "tmp-manual-pdfs"),
            "quarantine": _dir_stats(quarantine_root(vault_path)),
            "evolution": _dir_stats(evolution_root(vault_path)),
            "meta": _dir_stats(epi_meta_root(vault_path)),
        },
    }


def _unique_collision_path(path: Path) -> Path:
    counter = 1
    while True:
        candidate = path.with_name(f"{path.stem}-legacy-{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def _move_path_merge(source: Path, target: Path, actions: list[dict[str, Any]], *, dry_run: bool) -> None:
    if not source.exists():
        return
    if source.is_file():
        destination = target
        if destination.exists():
            destination = _unique_collision_path(destination)
        actions.append({"action": "move", "from": str(source), "to": str(destination)})
        if not dry_run:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(destination))
        return
    _merge_move_contents(source, target, actions, dry_run=dry_run)


def _merge_move_contents(source: Path, target: Path, actions: list[dict[str, Any]], *, dry_run: bool) -> None:
    if not source.exists():
        return
    if source.is_file():
        _move_path_merge(source, target, actions, dry_run=dry_run)
        return
    if not dry_run:
        target.mkdir(parents=True, exist_ok=True)
    for child in sorted(source.iterdir(), key=lambda item: item.name):
        destination = target / child.name
        if destination.exists():
            if child.is_dir() and destination.is_dir():
                _merge_move_contents(child, destination, actions, dry_run=dry_run)
                if not dry_run and child.exists() and not any(child.iterdir()):
                    child.rmdir()
                continue
            destination = _unique_collision_path(destination)
        actions.append({"action": "move", "from": str(child), "to": str(destination)})
        if not dry_run:
            shutil.move(str(child), str(destination))
    if not dry_run and source.exists() and not any(source.iterdir()):
        source.rmdir()


def migrate_legacy_epi_roots(vault_path: Path, *, dry_run: bool = False) -> dict[str, Any]:
    vault_path = vault_path.resolve()
    if not dry_run:
        ensure_epi_repository(vault_path)
    actions: list[dict[str, Any]] = []
    for legacy_name, new_relative in LEGACY_INTERNAL_ROOTS.items():
        source = vault_path / legacy_name
        target = epi_root(vault_path) / new_relative
        _merge_move_contents(source, target, actions, dry_run=dry_run)

    legacy_nested_raw = epi_root(vault_path) / "raw" / "papers"
    _merge_move_contents(legacy_nested_raw, raw_papers_root(vault_path), actions, dry_run=dry_run)

    legacy_meta = vault_path / "_meta"
    if legacy_meta.exists():
        internal_meta_names = {
            "epi-config.yaml",
            "epi-config-state.json",
            "epi-config-history",
            "config-history",
            "run-lifecycle",
            "wiki-reset",
        }
        for name in sorted(internal_meta_names):
            source = legacy_meta / name
            if source.exists():
                _move_path_merge(source, epi_meta_root(vault_path) / name, actions, dry_run=dry_run)

    result = {
        "schema_version": "epi-repository-migration-v1",
        "status": "preview" if dry_run else "migrated",
        "migrated_at": utc_now(),
        "vault_path": str(vault_path),
        "epi_root": str(epi_root(vault_path)),
        "actions": actions,
    }
    if not dry_run:
        manifest_path = epi_meta_root(vault_path) / "migrations" / f"{utc_now().replace(':', '').replace('+', 'Z')}-legacy-roots.json"
        write_json_atomic(manifest_path, result)
        result["manifest_path"] = str(manifest_path)
        refresh_epi_manifest(vault_path)
    return result


def load_retention_policy(vault_path: Path, *, ensure: bool = True) -> dict[str, Any]:
    if ensure:
        ensure_epi_repository(vault_path)
    policy_path = policies_root(vault_path) / "retention.json"
    try:
        import json

        payload = json.loads(policy_path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload = _upgrade_legacy_default_retention_policy(payload)
    policy = dict(DEFAULT_RETENTION_POLICY)
    for key, value in payload.items():
        if isinstance(value, dict) and isinstance(policy.get(key), dict):
            merged = dict(policy[key])
            merged.update(value)
            policy[key] = merged
        else:
            policy[key] = value
    if ensure and policy_path.exists() and payload:
        try:
            import json

            current = json.loads(policy_path.read_text(encoding="utf-8"))
        except Exception:
            current = {}
        if current != payload:
            write_json_atomic(policy_path, payload)
    return policy


def _upgrade_legacy_default_retention_policy(payload: dict[str, Any]) -> dict[str, Any]:
    legacy_default = (
        payload.get("max_total_files") == 12000
        and payload.get("max_total_bytes") == 5 * 1024 * 1024 * 1024
        and "lifecycle" not in payload
        and "raw/papers" in payload.get("protected", [])
    )
    if not legacy_default:
        return payload
    upgraded = dict(DEFAULT_RETENTION_POLICY)
    for key in ["schema_version", "auto_cleanup_enabled", "runs", "staging"]:
        if key in payload:
            upgraded[key] = payload[key]
    return upgraded


def _path_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _remove_tree(path: Path) -> tuple[int, int]:
    stats = _dir_stats(path)
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        stats = {"file_count": 1, "total_bytes": path.stat().st_size}
        path.unlink()
    return stats["file_count"], stats["total_bytes"]


def _is_terminal_run_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    try:
        import json

        state = json.loads((path / "run-state.json").read_text(encoding="utf-8"))
    except Exception:
        return True
    status = str(state.get("status") or state.get("state") or "").lower()
    return status not in {"running", "waiting_for_human_gate"}


def _keep_latest_count(config: object, default: int) -> int:
    if isinstance(config, dict):
        value = config.get("keep_latest", default)
    else:
        value = default
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _prune_children_by_mtime(
    *,
    root: Path,
    keep_latest: int,
    action: str,
    actions: list[dict[str, Any]],
    dry_run: bool,
    files_only: bool = False,
    dirs_only: bool = False,
) -> None:
    if not root.exists():
        return
    children = []
    for child in root.iterdir():
        if files_only and not child.is_file():
            continue
        if dirs_only and not child.is_dir():
            continue
        children.append(child)
    children.sort(key=_path_mtime)
    removable = children[:-keep_latest] if keep_latest > 0 else children
    for child in removable:
        file_count, total_bytes = _dir_stats(child) if child.is_dir() else (1, child.stat().st_size)
        actions.append(
            {
                "action": action,
                "path": str(child),
                "file_count": file_count,
                "total_bytes": total_bytes,
            }
        )
        if not dry_run:
            _remove_tree(child)


def _collect_lifecycle_cleanup_actions(
    vault_path: Path,
    policy: dict[str, Any],
    actions: list[dict[str, Any]],
    *,
    dry_run: bool,
) -> None:
    lifecycle = policy.get("lifecycle") if isinstance(policy.get("lifecycle"), dict) else {}
    meta_policy = lifecycle.get("meta_manifests") if isinstance(lifecycle.get("meta_manifests"), dict) else {}
    for meta_name, default_keep in {
        "run-lifecycle": 20,
        "raw-cleanup": 30,
        "repository-maintenance": 20,
        "migrations": 20,
        "wiki-reset": 10,
    }.items():
        keep_latest = _keep_latest_count(meta_policy.get(meta_name), default_keep)
        _prune_children_by_mtime(
            root=epi_meta_root(vault_path) / meta_name,
            keep_latest=keep_latest,
            action=f"remove-old-meta-{meta_name}",
            actions=actions,
            dry_run=dry_run,
            files_only=True,
        )

    snapshot_policy = lifecycle.get("formal_page_snapshots")
    _prune_children_by_mtime(
        root=epi_meta_root(vault_path) / "formal-page-snapshots",
        keep_latest=_keep_latest_count(snapshot_policy, 3),
        action="remove-old-formal-page-snapshot",
        actions=actions,
        dry_run=dry_run,
        dirs_only=True,
    )

    temporary_policy = lifecycle.get("temporary_files") if isinstance(lifecycle.get("temporary_files"), dict) else {}
    _prune_children_by_mtime(
        root=epi_root(vault_path) / "tmp-manual-pdfs",
        keep_latest=_keep_latest_count(temporary_policy.get("tmp-manual-pdfs"), 5),
        action="remove-old-temporary-manual-pdf",
        actions=actions,
        dry_run=dry_run,
        files_only=True,
    )


def _collect_empty_on_demand_dir_cleanup_actions(
    vault_path: Path,
    actions: list[dict[str, Any]],
    *,
    dry_run: bool,
) -> None:
    root = epi_root(vault_path)
    on_demand_roots = [
        root / "cache",
        root / "tmp",
        root / "tmp-manual-pdfs",
        root / "quarantine",
        root / "evolution",
    ]
    for on_demand_root in on_demand_roots:
        if not on_demand_root.exists() or not on_demand_root.is_dir():
            continue
        empty_dirs = [
            path
            for path in on_demand_root.rglob("*")
            if path.is_dir() and not any(path.iterdir())
        ]
        empty_dirs.append(on_demand_root)
        empty_dirs.sort(key=lambda path: len(path.parts), reverse=True)
        for path in empty_dirs:
            if not path.exists() or not path.is_dir() or any(path.iterdir()):
                continue
            actions.append(
                {
                    "action": "remove-empty-on-demand-dir",
                    "path": str(path),
                    "file_count": 0,
                    "total_bytes": 0,
                }
            )
            if not dry_run:
                path.rmdir()


def cleanup_epi_repository(vault_path: Path, *, dry_run: bool = False) -> dict[str, Any]:
    vault_path = vault_path.resolve()
    if not dry_run:
        ensure_epi_repository(vault_path)
    policy = load_retention_policy(vault_path, ensure=not dry_run)
    before = inspect_epi_manifest(vault_path) if dry_run else refresh_epi_manifest(vault_path)
    root_stats = _dir_stats(epi_root(vault_path))
    max_files = int(policy.get("max_total_files") or DEFAULT_RETENTION_POLICY["max_total_files"])
    max_bytes = int(policy.get("max_total_bytes") or DEFAULT_RETENTION_POLICY["max_total_bytes"])
    actions: list[dict[str, Any]] = []

    over_budget = root_stats["file_count"] > max_files or root_stats["total_bytes"] > max_bytes
    auto_cleanup_enabled = bool(policy.get("auto_cleanup_enabled", True))
    lifecycle_policy = policy.get("lifecycle") if isinstance(policy.get("lifecycle"), dict) else {}
    enforce_lifecycle = bool(lifecycle_policy.get("enforce_even_when_under_budget", True))
    if auto_cleanup_enabled and (over_budget or enforce_lifecycle):
        run_dirs = [
            path
            for path in runs_root(vault_path).iterdir()
            if path.is_dir() and _is_terminal_run_dir(path)
        ] if runs_root(vault_path).exists() else []
        run_dirs.sort(key=_path_mtime)
        keep_latest = int((policy.get("runs") or {}).get("keep_latest", 15))
        removable = run_dirs[:-keep_latest] if keep_latest > 0 else run_dirs
        for run_dir in removable:
            run_stats = _dir_stats(run_dir)
            file_count = run_stats["file_count"]
            total_bytes = run_stats["total_bytes"]
            actions.append(
                {
                    "action": "remove-terminal-run-dir",
                    "path": str(run_dir),
                    "file_count": file_count,
                    "total_bytes": total_bytes,
                }
            )
            if not dry_run:
                _remove_tree(run_dir)
            root_stats["file_count"] -= file_count
            root_stats["total_bytes"] -= total_bytes
            if over_budget and root_stats["file_count"] <= max_files and root_stats["total_bytes"] <= max_bytes:
                break
        if enforce_lifecycle:
            _collect_lifecycle_cleanup_actions(vault_path, policy, actions, dry_run=dry_run)
    if auto_cleanup_enabled:
        _collect_empty_on_demand_dir_cleanup_actions(vault_path, actions, dry_run=dry_run)

    after = refresh_epi_manifest(vault_path) if not dry_run else inspect_epi_manifest(vault_path)
    result = {
        "schema_version": "epi-repository-cleanup-v1",
        "status": "preview" if dry_run else "cleaned",
        "checked_at": utc_now(),
        "vault_path": str(vault_path),
        "epi_root": str(epi_root(vault_path)),
        "policy": {
            "max_total_files": max_files,
            "max_total_bytes": max_bytes,
            "auto_cleanup_enabled": auto_cleanup_enabled,
            "lifecycle_enforced": enforce_lifecycle,
        },
        "over_budget": over_budget,
        "actions": actions,
        "deleted_count": len(actions),
        "before_stats": before.get("stats", {}),
        "after_stats": after.get("stats", {}),
    }
    if not dry_run and (over_budget or actions):
        manifest_path = (
            epi_meta_root(vault_path)
            / "repository-maintenance"
            / f"{utc_now().replace(':', '').replace('+', 'Z')}-cleanup.json"
        )
        write_json_atomic(manifest_path, result)
        result["manifest_path"] = str(manifest_path)
    return result
