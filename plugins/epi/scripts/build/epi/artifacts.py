from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EPI_ROOT_NAME = "_epi"
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


def epi_root(vault_path: Path) -> Path:
    return vault_path.resolve() / EPI_ROOT_NAME


def raw_root(vault_path: Path) -> Path:
    return epi_root(vault_path) / "raw"


def raw_papers_root(vault_path: Path) -> Path:
    return raw_root(vault_path)


def raw_paper_root(vault_path: Path, slug: str) -> Path:
    return raw_papers_root(vault_path) / slug


def legacy_raw_paper_root(vault_path: Path, slug: str) -> Path:
    return vault_path.resolve() / LEGACY_RAW_ROOT_NAME / "papers" / slug


def legacy_nested_epi_raw_paper_root(vault_path: Path, slug: str) -> Path:
    return raw_root(vault_path) / "papers" / slug


def existing_raw_paper_root(vault_path: Path, slug: str) -> Path:
    current = raw_paper_root(vault_path, slug)
    if current.exists():
        return current
    legacy_nested = legacy_nested_epi_raw_paper_root(vault_path, slug)
    if legacy_nested.exists():
        return legacy_nested
    legacy = legacy_raw_paper_root(vault_path, slug)
    if legacy.exists():
        return legacy
    return current


def staging_root(vault_path: Path) -> Path:
    return epi_root(vault_path) / "staging"


def staging_papers_root(vault_path: Path) -> Path:
    return staging_root(vault_path) / "papers"


def staging_paper_root(vault_path: Path, slug: str) -> Path:
    return staging_papers_root(vault_path) / slug


def legacy_staging_paper_root(vault_path: Path, slug: str) -> Path:
    return vault_path.resolve() / LEGACY_STAGING_ROOT_NAME / "papers" / slug


def existing_staging_paper_root(vault_path: Path, slug: str) -> Path:
    current = staging_paper_root(vault_path, slug)
    if current.exists():
        return current
    legacy = legacy_staging_paper_root(vault_path, slug)
    if legacy.exists():
        return legacy
    return current


def wiki_batches_root(vault_path: Path) -> Path:
    return staging_root(vault_path) / "wiki-batches"


def wiki_batch_pending_root(vault_path: Path) -> Path:
    return wiki_batches_root(vault_path) / "pending"


def runs_root(vault_path: Path) -> Path:
    return epi_root(vault_path) / "runs"


def legacy_runs_root(vault_path: Path) -> Path:
    return vault_path.resolve() / LEGACY_RUNS_ROOT_NAME


def existing_runs_root(vault_path: Path) -> Path:
    current = runs_root(vault_path)
    if current.exists():
        return current
    legacy = legacy_runs_root(vault_path)
    if legacy.exists():
        return legacy
    return current


def existing_run_dir(vault_path: Path, run_id: str) -> Path:
    current = runs_root(vault_path) / run_id
    if current.exists():
        return current
    legacy = legacy_runs_root(vault_path) / run_id
    if legacy.exists():
        return legacy
    return current


def quarantine_root(vault_path: Path) -> Path:
    return epi_root(vault_path) / "quarantine"


def evolution_root(vault_path: Path) -> Path:
    return epi_root(vault_path) / "evolution"


def epi_meta_root(vault_path: Path) -> Path:
    return epi_root(vault_path) / "meta"


def legacy_meta_root(vault_path: Path) -> Path:
    return vault_path.resolve() / LEGACY_META_ROOT_NAME


def policies_root(vault_path: Path) -> Path:
    return epi_root(vault_path) / "policies"


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
