from __future__ import annotations

from pathlib import Path
from typing import Any

from epi.artifacts import file_sha256
from epi.source_artifacts import resolved_mineru_markdown_relative_path, source_first_artifacts


def _file_record(paper_root: Path, artifact: str) -> dict[str, Any]:
    path = paper_root / artifact
    record: dict[str, Any] = {
        "artifact": artifact,
        "exists": path.is_file(),
        "path": str(path),
    }
    if path.is_file():
        record["sha256"] = file_sha256(path)
        record["size_bytes"] = path.stat().st_size
    return record


def _image_record(paper_root: Path) -> dict[str, Any]:
    image_dir = paper_root / "mineru" / "images"
    image_files = sorted(path for path in image_dir.rglob("*") if path.is_file()) if image_dir.exists() else []
    return {
        "artifact": "mineru/images/*",
        "exists": bool(image_files),
        "path": str(image_dir),
        "file_count": len(image_files),
        "files": [
            {
                "relative_path": path.relative_to(paper_root).as_posix(),
                "sha256": file_sha256(path),
                "size_bytes": path.stat().st_size,
            }
            for path in image_files
        ],
    }


def audit_source_bundle(paper_root: Path) -> dict[str, Any]:
    """Inspect the source-first raw bundle that EPI must preserve before wiki handoff."""

    paper_root = paper_root.resolve()
    artifacts = source_first_artifacts(paper_root)
    artifact_records: dict[str, dict[str, Any]] = {}
    missing_artifacts: list[str] = []
    for artifact in artifacts:
        if artifact == "mineru/images/*":
            record = _image_record(paper_root)
        else:
            record = _file_record(paper_root, artifact)
        artifact_records[artifact] = record
        if not record.get("exists"):
            missing_artifacts.append(artifact)
    return {
        "schema_version": "epi-source-bundle-audit-v1",
        "paper_slug": paper_root.name,
        "paper_root": str(paper_root),
        "status": "complete" if not missing_artifacts else "incomplete",
        "complete": not missing_artifacts,
        "required_artifacts": artifacts,
        "missing_artifacts": missing_artifacts,
        "mineru_markdown": resolved_mineru_markdown_relative_path(paper_root),
        "artifact_records": artifact_records,
    }
