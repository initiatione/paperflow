from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "paper-research-reference-index-v1"
FRONTMATTER = re.compile(r"\A---\r?\n(?P<frontmatter>.*?)\r?\n---\r?\n?", re.DOTALL)
SOURCE_PDF = re.compile(r"_paper_source%2Fraw%2F(?P<slug>[^%/]+)%2Fpaper\.pdf", re.IGNORECASE)
DOI_URL = re.compile(r"https?://(?:dx\.)?doi\.org/(?P<doi>10\.\S+)", re.IGNORECASE)
ARXIV_URL = re.compile(r"arxiv\.org/(?:abs|pdf)/(?P<arxiv>\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _slugify(value: object) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "untitled-paper"


def _normalize_title(value: object) -> str:
    text = str(value or "").lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _normalize_doi(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = re.sub(r"^doi:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", text, flags=re.IGNORECASE)
    text = text.strip().rstrip(".,;)")
    if text.lower() in {"null", "none", "未核实", "缺失"}:
        return None
    return text.lower()


def _normalize_arxiv_base_id(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = re.sub(r"^arxiv:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^https?://arxiv\.org/(?:abs|pdf)/", "", text, flags=re.IGNORECASE)
    text = text.removesuffix(".pdf").strip().rstrip(".,;)")
    match = re.search(r"(\d{4}\.\d{4,5})(?:v\d+)?", text)
    if match:
        return match.group(1)
    return text or None


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"", "null", "Null", "NULL", "~"}:
        return None
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def _parse_frontmatter(text: str) -> dict[str, Any]:
    match = FRONTMATTER.match(text)
    if not match:
        return {}
    result: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in match.group("frontmatter").splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item_match = re.match(r"^\s*-\s+(.*)$", line)
        if item_match and current_key:
            result.setdefault(current_key, []).append(_parse_scalar(item_match.group(1)))
            continue
        key_match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if key_match:
            key, value = key_match.groups()
            current_key = key
            if value == "":
                result[key] = []
            else:
                result[key] = _parse_scalar(value)
    return result


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return [item for item in value if item not in {None, ""}]
    if value in {None, ""}:
        return []
    return [value]


def _first(value: Any) -> Any:
    values = _as_list(value)
    return values[0] if values else None


def _extract_source_slug(frontmatter: dict[str, Any], text: str) -> str | None:
    sources = " ".join(str(item) for item in _as_list(frontmatter.get("sources")))
    match = SOURCE_PDF.search(sources) or SOURCE_PDF.search(text)
    return match.group("slug") if match else None


def _extract_doi(frontmatter: dict[str, Any], text: str) -> str | None:
    doi = _normalize_doi(frontmatter.get("doi"))
    if doi:
        return doi
    match = DOI_URL.search(text)
    return _normalize_doi(match.group("doi")) if match else None


def _extract_arxiv(frontmatter: dict[str, Any], text: str) -> tuple[str | None, str | None]:
    arxiv_id = str(frontmatter.get("arxiv_id") or frontmatter.get("arxiv") or "").strip() or None
    if not arxiv_id:
        match = ARXIV_URL.search(text)
        arxiv_id = match.group("arxiv") if match else None
    return arxiv_id, _normalize_arxiv_base_id(arxiv_id)


def _dedupe_keys(entry: dict[str, Any]) -> list[str]:
    keys: list[str] = []

    def add(key: str | None) -> None:
        if key and key not in keys:
            keys.append(key)

    add(f"doi:{entry.get('doi')}" if entry.get("doi") else None)
    add(f"arxiv:{entry.get('arxiv_base_id')}" if entry.get("arxiv_base_id") else None)
    add(f"source_id:{entry.get('source_id')}" if entry.get("source_id") else None)
    add(f"title:{entry.get('normalized_title')}" if entry.get("normalized_title") else None)
    return keys


def _entry_from_reference_page(vault: Path, page: Path) -> dict[str, Any]:
    text = page.read_text(encoding="utf-8")
    frontmatter = _parse_frontmatter(text)
    title = str(frontmatter.get("title") or page.stem.replace("-", " ")).strip()
    normalized_title = _normalize_title(frontmatter.get("normalized_title") or title)
    source_slug = _extract_source_slug(frontmatter, text)
    source_id = str(frontmatter.get("source_id") or source_slug or page.stem).strip()
    doi = _extract_doi(frontmatter, text)
    arxiv_id, arxiv_base_id = _extract_arxiv(frontmatter, text)
    relative_page = page.relative_to(vault).as_posix()
    entry = {
        "title": title,
        "normalized_title": normalized_title,
        "page": relative_page,
        "source_id": source_id,
        "source_id_mode": "frontmatter" if frontmatter.get("source_id") else "inferred_from_sources_pdf",
        "doi": doi,
        "arxiv_id": arxiv_id,
        "arxiv_base_id": arxiv_base_id,
        "year": frontmatter.get("year"),
        "venue": frontmatter.get("venue"),
        "authors": _as_list(frontmatter.get("authors")),
        "canonical_pdf": (
            f"obsidian://open?vault={vault.name}&file=_paper_source%2Fraw%2F{source_slug}%2Fpaper.pdf"
            if source_slug
            else None
        ),
        "external_pdf_url": frontmatter.get("external_pdf_url") or frontmatter.get("pdf_url"),
        "url": frontmatter.get("url") or (f"https://doi.org/{doi}" if doi else None),
        "github": frontmatter.get("github") or frontmatter.get("code_url"),
        "citation_count": frontmatter.get("citation_count"),
        "tags": _as_list(frontmatter.get("tags")),
        "aliases": _as_list(frontmatter.get("aliases")),
        "summary": frontmatter.get("summary"),
        "lifecycle": frontmatter.get("lifecycle"),
        "tier": frontmatter.get("tier"),
        "created": frontmatter.get("created"),
        "updated": frontmatter.get("updated"),
        "status": frontmatter.get("status") or "deposited",
        "page_sha256": _sha256(page),
        "page_size_bytes": page.stat().st_size,
    }
    entry["dedupe_keys"] = _dedupe_keys(entry)
    return entry


def _entry_from_raw_metadata(vault: Path, metadata_path: Path) -> dict[str, Any] | None:
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(metadata, dict):
        return None
    paper_root = metadata_path.parent
    title = str(metadata.get("title") or paper_root.name).strip()
    source_id = str(metadata.get("source_id") or metadata.get("slug") or paper_root.name).strip()
    arxiv_id = metadata.get("arxiv_id")
    arxiv_base_id = metadata.get("arxiv_base_id") or _normalize_arxiv_base_id(arxiv_id or metadata.get("url"))
    doi = _normalize_doi(metadata.get("doi"))
    entry = {
        "title": title,
        "normalized_title": _normalize_title(metadata.get("normalized_title") or title),
        "page": None,
        "source_id": source_id,
        "source_id_mode": "raw_metadata",
        "doi": doi,
        "arxiv_id": arxiv_id,
        "arxiv_base_id": arxiv_base_id,
        "year": metadata.get("year"),
        "venue": metadata.get("venue"),
        "authors": _as_list(metadata.get("authors")),
        "canonical_pdf": f"obsidian://open?vault={vault.name}&file=_paper_source%2Fraw%2F{paper_root.name}%2Fpaper.pdf",
        "external_pdf_url": metadata.get("pdf_url") or metadata.get("external_pdf_url"),
        "url": metadata.get("url") or (f"https://doi.org/{doi}" if doi else None),
        "github": metadata.get("github") or metadata.get("code_url"),
        "citation_count": metadata.get("citation_count"),
        "tags": _as_list(metadata.get("tags")),
        "aliases": _as_list(metadata.get("aliases")),
        "summary": metadata.get("summary"),
        "lifecycle": metadata.get("lifecycle"),
        "tier": metadata.get("tier"),
        "created": metadata.get("created"),
        "updated": metadata.get("updated"),
        "status": metadata.get("status") or "collected",
        "page_sha256": None,
        "page_size_bytes": None,
    }
    entry["dedupe_keys"] = _dedupe_keys(entry)
    return entry


def build_reference_index(vault_path: Path) -> dict[str, Any]:
    vault = Path(vault_path).resolve()
    entries_by_source_id: dict[str, dict[str, Any]] = {}

    references_root = vault / "references"
    if references_root.exists():
        for page in sorted(references_root.glob("*.md")):
            entry = _entry_from_reference_page(vault, page)
            entries_by_source_id[entry["source_id"]] = entry

    raw_root = vault / "_paper_source" / "raw"
    if raw_root.exists():
        for metadata_path in sorted(raw_root.glob("*/metadata.json")):
            entry = _entry_from_raw_metadata(vault, metadata_path)
            if not entry:
                continue
            entries_by_source_id.setdefault(entry["source_id"], entry)

    entries = sorted(entries_by_source_id.values(), key=lambda item: str(item.get("title") or "").lower())
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "vault": vault.name,
        "purpose": "Canonical lightweight reference backlog and dedupe index for Paper Source search and Paper Wiki maintenance.",
        "source_roots": ["references/*.md", "_paper_source/raw/<source_id>/metadata.json"],
        "dedupe_priority": ["doi", "arxiv_base_id", "source_id", "normalized_title"],
        "record_count": len(entries),
        "entries": entries,
    }


def refresh_reference_index(vault_path: Path) -> dict[str, Any]:
    vault = Path(vault_path).resolve()
    payload = build_reference_index(vault)
    path = vault / "_meta" / "reference-index.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"path": str(path), "record_count": payload["record_count"], "schema_version": SCHEMA_VERSION}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh Paper Wiki _meta/reference-index.json")
    parser.add_argument("--vault", required=True, help="Path to the target Paper Wiki vault")
    parser.add_argument("--json", action="store_true", help="Print machine-readable refresh result")
    args = parser.parse_args(argv)
    result = refresh_reference_index(Path(args.vault))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"refreshed {result['path']} ({result['record_count']} records)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
