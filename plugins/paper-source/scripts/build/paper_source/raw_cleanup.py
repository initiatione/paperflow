from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from paper_source.artifacts import (
    paper_source_meta_root,
    raw_paper_root,
    raw_papers_root,
    read_json_dict,
    staging_paper_root,
    utc_now,
    write_json_atomic,
)
from paper_source.source_artifacts import resolve_mineru_markdown_path


def _has_complete_parse(paper_root: Path) -> bool:
    parse_record = read_json_dict(paper_root / "parse-record.json", default=None) or {}
    mineru_dir = paper_root / "mineru"
    return (
        parse_record.get("status") == "success"
        and (paper_root / "paper.pdf").is_file()
        and resolve_mineru_markdown_path(paper_root).is_file()
        and (mineru_dir / "mineru-manifest.json").is_file()
        and (mineru_dir / "images").is_dir()
    )


def _stage_record_summary(stage_record: dict | None) -> dict[str, Any]:
    if not isinstance(stage_record, dict):
        return {}
    keys = [
        "stage",
        "mode",
        "status",
        "exit_status",
        "failure_class",
        "retryable",
        "http_status",
        "error_type",
        "error",
        "recovery_hint",
    ]
    return {key: stage_record[key] for key in keys if key in stage_record}


def _raw_cleanup_root(vault_path: Path) -> Path:
    return paper_source_meta_root(vault_path) / "raw-cleanup"


def _write_cleanup_manifest(vault_path: Path, record: dict[str, Any]) -> Path:
    root = _raw_cleanup_root(vault_path)
    root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    slug = str(record.get("slug") or "unknown")
    path = root / f"{timestamp}-{slug}.json"
    write_json_atomic(path, record)
    return path


def _relative_files(root: Path) -> list[str]:
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            files.append(path.relative_to(root).as_posix())
    return files


def cleanup_failed_raw_paper(
    vault_path: Path,
    slug: str,
    *,
    reason: str = "failed_before_complete_parse",
    stage_record: dict | None = None,
) -> dict[str, Any]:
    vault_path = Path(vault_path).resolve()
    paper_root = raw_paper_root(vault_path, slug)
    papers_root = raw_papers_root(vault_path)
    record: dict[str, Any] = {
        "schema_version": "paper-source-raw-cleanup-v1",
        "slug": slug,
        "path": str(paper_root),
        "reason": reason,
        "stage_record": _stage_record_summary(stage_record),
        "created_at": utc_now(),
    }
    if not paper_root.exists():
        record["status"] = "skipped"
        record["skip_reason"] = "raw_folder_missing"
        return record
    resolved_root = paper_root.resolve()
    if resolved_root.parent != papers_root.resolve():
        record["status"] = "skipped"
        record["skip_reason"] = "path_outside_raw_root"
        return record
    if (paper_root / "paper.pdf").is_file():
        record["status"] = "skipped"
        record["skip_reason"] = "source_pdf_present"
        return record
    if (
        (isinstance(stage_record, dict) and stage_record.get("failure_class") == "identity-mismatch")
        or (paper_root / "identity-check.json").is_file()
    ):
        record["status"] = "skipped"
        record["skip_reason"] = "identity_mismatch_quarantined"
        return record
    if _has_complete_parse(paper_root):
        record["status"] = "skipped"
        record["skip_reason"] = "complete_parse_present"
        return record
    if (staging_paper_root(vault_path, slug) / "promotion-plan.json").exists():
        record["status"] = "skipped"
        record["skip_reason"] = "staging_present"
        return record
    if (paper_root / "wiki-ingest-record.json").exists() or (paper_root / "zotero-record.json").exists():
        record["status"] = "skipped"
        record["skip_reason"] = "downstream_record_present"
        return record

    files = _relative_files(paper_root)
    record["status"] = "deleted"
    record["deleted_at"] = utc_now()
    record["deleted_file_count"] = len(files)
    record["deleted_files"] = files
    shutil.rmtree(paper_root)
    manifest_path = _write_cleanup_manifest(vault_path, record)
    record["manifest_path"] = str(manifest_path)
    write_json_atomic(manifest_path, record)
    return record
