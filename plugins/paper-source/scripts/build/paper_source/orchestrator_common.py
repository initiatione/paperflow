from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from paper_source.artifacts import file_sha256, raw_paper_root, runs_root
from paper_source.paper_source_repository import (
    cleanup_paper_source_repository,
    ensure_paper_source_repository,
    refresh_paper_source_manifest,
)
from paper_source.rank_papers import SELECTION_POLICIES
from paper_source.raw_cleanup import cleanup_failed_raw_paper
from paper_source.run_index import auto_prune_run_lifecycle, refresh_run_index

_LOCAL_TOOL_VERSION = "paper-source-local"


def _refresh_run_index(vault_path: Path) -> None:
    refresh_run_index(vault_path.resolve())


def _auto_manage_run_lifecycle(vault_path: Path) -> dict:
    result = auto_prune_run_lifecycle(
        vault_path.resolve(),
        keep_latest=15,
        keep_per_workflow=2,
    )
    repository_cleanup = cleanup_paper_source_repository(vault_path)
    if repository_cleanup.get("deleted_count"):
        result["repository_cleanup"] = repository_cleanup
        result["deleted_count"] = int(result.get("deleted_count", 0)) + int(repository_cleanup.get("deleted_count", 0))
    else:
        refresh_paper_source_manifest(vault_path)
    return result


def _hash_paper_run_states(vault_path: Path, results: list[dict]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for result in results:
        slug = result.get("paper_slug")
        if not slug:
            continue
        run_state_path = raw_paper_root(vault_path, slug) / "run-state.json"
        if run_state_path.exists():
            hashes[f"paper:{slug}:run-state.json"] = file_sha256(run_state_path)
        raw_cleanup = result.get("raw_cleanup") if isinstance(result.get("raw_cleanup"), dict) else {}
        manifest_path = raw_cleanup.get("manifest_path")
        if manifest_path and Path(manifest_path).exists():
            hashes[f"paper:{slug}:raw-cleanup.json"] = file_sha256(Path(manifest_path))
    return hashes


def _cleanup_failed_prepare_raw_results(vault_path: Path, results: list[dict]) -> list[dict]:
    cleanup_records: list[dict] = []
    for result in results:
        state = str(result.get("state") or "")
        last_action = str(result.get("last_action") or "")
        slug = str(result.get("paper_slug") or "")
        if not slug or not state.endswith("_failed") or last_action not in {"acquire", "parse", "prepare"}:
            continue
        cleanup = cleanup_failed_raw_paper(
            vault_path,
            slug,
            reason="failed_before_complete_parse",
            stage_record=result.get("stage_record") if isinstance(result.get("stage_record"), dict) else None,
        )
        result["raw_cleanup"] = cleanup
        cleanup_records.append(cleanup)
    return cleanup_records


def _manual_downloads_from_results(results: list[dict]) -> list[dict]:
    cards: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for result in results:
        stage_record = result.get("stage_record")
        if not isinstance(stage_record, dict):
            continue
        manual_download = stage_record.get("manual_download")
        if not isinstance(manual_download, dict):
            continue
        card = dict(manual_download)
        card.setdefault("slug", result.get("paper_slug"))
        card.setdefault("paper_slug", result.get("paper_slug"))
        key = (
            str(card.get("slug") or ""),
            str(card.get("doi") or ""),
            str(card.get("doi_url") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        cards.append(card)
    return cards


def _hash_existing_outputs(paths: dict[str, Path]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for name, path in paths.items():
        if path.exists():
            hashes[name] = file_sha256(path)
    return hashes


def _tool_versions(*tool_names: str) -> dict[str, str]:
    return {tool_name: _LOCAL_TOOL_VERSION for tool_name in tool_names}


def _new_run_dir(vault_path: Path, prefix: str | None = None) -> tuple[str, Path]:
    ensure_paper_source_repository(vault_path)
    runs_dir = runs_root(vault_path)
    runs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_id = f"{prefix}-{timestamp}" if prefix else timestamp
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_id, run_dir


def _normalize_selection_policy(value: object) -> str:
    policy = str(value or "balanced_high_quality").strip().lower()
    if policy not in SELECTION_POLICIES:
        raise ValueError(f"unknown selection_policy: {value}")
    return policy
