from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PAPER_SOURCE_ROOT_NAME = "_paper_source"
# Historical roots are for explicit migration, reset cleanup, or repair diagnostics only.
# Normal runtime helpers must resolve to the current Paper Source root.
LEGACY_EPI_ROOT_NAME = "_epi"
LEGACY_RAW_ROOT_NAME = "_raw"
LEGACY_STAGING_ROOT_NAME = "_staging"
LEGACY_RUNS_ROOT_NAME = "_runs"
LEGACY_QUARANTINE_ROOT_NAME = "_quarantine"
LEGACY_EVOLUTION_ROOT_NAME = "_evolution"
LEGACY_META_ROOT_NAME = "_meta"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_sha256(payload: Any) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def paper_source_root(vault_path: Path) -> Path:
    return _vault_path(vault_path, PAPER_SOURCE_ROOT_NAME)


def _vault_path(vault_path: Path, *parts: str) -> Path:
    return vault_path.resolve().joinpath(*parts)


def _paper_source_path(vault_path: Path, *parts: str) -> Path:
    return _vault_path(vault_path, PAPER_SOURCE_ROOT_NAME, *parts)


def paper_source_meta_root(vault_path: Path) -> Path:
    return _paper_source_path(vault_path, "meta")


def legacy_epi_root(vault_path: Path) -> Path:
    return _vault_path(vault_path, LEGACY_EPI_ROOT_NAME)


def existing_paper_source_root(vault_path: Path) -> Path:
    return paper_source_root(vault_path)


def raw_root(vault_path: Path) -> Path:
    return _paper_source_path(vault_path, "raw")


def raw_papers_root(vault_path: Path) -> Path:
    return raw_root(vault_path)


def raw_paper_root(vault_path: Path, slug: str) -> Path:
    return raw_papers_root(vault_path) / slug


def legacy_raw_paper_root(vault_path: Path, slug: str) -> Path:
    return _vault_path(vault_path, LEGACY_RAW_ROOT_NAME, "papers", slug)


def legacy_nested_epi_raw_paper_root(vault_path: Path, slug: str) -> Path:
    return _vault_path(vault_path, LEGACY_EPI_ROOT_NAME, "raw", "papers", slug)


def legacy_epi_raw_paper_root(vault_path: Path, slug: str) -> Path:
    return _vault_path(vault_path, LEGACY_EPI_ROOT_NAME, "raw", slug)


def existing_raw_paper_root(vault_path: Path, slug: str) -> Path:
    return raw_paper_root(vault_path, slug)


def staging_root(vault_path: Path) -> Path:
    return _paper_source_path(vault_path, "staging")


def staging_papers_root(vault_path: Path) -> Path:
    return staging_root(vault_path) / "papers"


def staging_paper_root(vault_path: Path, slug: str) -> Path:
    return staging_papers_root(vault_path) / slug


def legacy_staging_paper_root(vault_path: Path, slug: str) -> Path:
    return _vault_path(vault_path, LEGACY_STAGING_ROOT_NAME, "papers", slug)


def legacy_epi_staging_paper_root(vault_path: Path, slug: str) -> Path:
    return _vault_path(vault_path, LEGACY_EPI_ROOT_NAME, "staging", "papers", slug)


def existing_staging_paper_root(vault_path: Path, slug: str) -> Path:
    return staging_paper_root(vault_path, slug)


def wiki_batches_root(vault_path: Path) -> Path:
    return staging_root(vault_path) / "wiki-batches"


def wiki_batch_pending_root(vault_path: Path) -> Path:
    return wiki_batches_root(vault_path) / "pending"


def runs_root(vault_path: Path) -> Path:
    return _paper_source_path(vault_path, "runs")


def reviews_root(vault_path: Path) -> Path:
    return _paper_source_path(vault_path, "reviews")


def review_root(vault_path: Path, review_id: str) -> Path:
    return reviews_root(vault_path) / review_id


def legacy_runs_root(vault_path: Path) -> Path:
    return _vault_path(vault_path, LEGACY_RUNS_ROOT_NAME)


def legacy_epi_runs_root(vault_path: Path) -> Path:
    return _vault_path(vault_path, LEGACY_EPI_ROOT_NAME, "runs")


def existing_runs_root(vault_path: Path) -> Path:
    return runs_root(vault_path)


def existing_run_dir(vault_path: Path, run_id: str) -> Path:
    return runs_root(vault_path) / run_id


def quarantine_root(vault_path: Path) -> Path:
    return _paper_source_path(vault_path, "quarantine")


def evolution_root(vault_path: Path) -> Path:
    return _paper_source_path(vault_path, "evolution")


def legacy_meta_root(vault_path: Path) -> Path:
    return _vault_path(vault_path, LEGACY_META_ROOT_NAME)


def policies_root(vault_path: Path) -> Path:
    return _paper_source_path(vault_path, "policies")


def vault_relative(vault_path: Path, path: Path) -> str:
    return path.resolve().relative_to(vault_path.resolve()).as_posix()


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp_path, path)


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(content, encoding="utf-8")
    os.replace(temp_path, path)


_MISSING = object()


def read_json(path: Path, *, default: Any = _MISSING) -> Any:
    """Read and parse JSON from ``path``.

    On a missing file, unreadable file, or invalid JSON, return ``default`` when
    it is provided; otherwise re-raise the original error. This centralizes the
    read-with-fallback pattern that individual modules previously reimplemented.
    """
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        if default is _MISSING:
            raise
        return default


def read_json_dict(path: Path, *, default: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Read a JSON object from ``path``.

    Return the parsed object when it is a dict. On a missing file, unreadable
    file, invalid JSON, or a non-dict payload, return a fresh copy of ``default``
    (or ``None`` when ``default`` is ``None``).
    """
    payload = read_json(path, default=None)
    if isinstance(payload, dict):
        return payload
    return dict(default) if default is not None else None
