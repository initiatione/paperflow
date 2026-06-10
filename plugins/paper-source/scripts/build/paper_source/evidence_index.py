from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from paper_source.artifacts import (
    file_sha256,
    paper_source_meta_root,
    raw_paper_root,
    utc_now,
    vault_relative,
    write_json_atomic,
)
from paper_source.source_artifacts import (
    has_nonempty_mineru_tex,
    resolve_mineru_markdown_path,
    resolved_mineru_markdown_relative_path,
)

PAGE_MARKER = re.compile(
    r"^\s*(?:\[\[page:(\d+)\]\]|<!--\s*page[:=\s]+(\d+)\s*-->|-{3,}\s*page\s+(\d+)\s*-{3,})\s*$",
    re.IGNORECASE,
)
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def _load_metadata(paper_root: Path) -> dict[str, Any]:
    try:
        payload = json.loads((paper_root / "metadata.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _chunk_hash(payload: dict[str, Any]) -> str:
    basis = json.dumps(
        {
            "page": payload.get("page"),
            "section_path": payload.get("section_path"),
            "text": payload.get("text"),
            "source_locator": payload.get("source_locator"),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def _slug_fragment(section_path: list[str], chunk_index: int) -> str:
    section = "-".join(section_path[-2:]) if section_path else "document"
    section = re.sub(r"[^a-z0-9]+", "-", section.lower()).strip("-") or "document"
    return f"{section}:c{chunk_index:04d}"


def _split_paragraph_chunks(text: str, max_chars: int, overlap_chars: int) -> list[tuple[int, int, str]]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    chunks: list[tuple[int, int, str]] = []
    offset = 0
    current: list[str] = []
    current_start = 0
    current_len = 0
    for paragraph in paragraphs:
        paragraph_start = text.find(paragraph, offset)
        if paragraph_start < 0:
            paragraph_start = offset
        candidate_len = current_len + (2 if current else 0) + len(paragraph)
        if current and candidate_len > max_chars:
            chunk_text = "\n\n".join(current)
            chunks.append((current_start, current_start + len(chunk_text), chunk_text))
            overlap = chunk_text[-overlap_chars:].strip() if overlap_chars > 0 else ""
            current = [overlap, paragraph] if overlap else [paragraph]
            current_start = max(paragraph_start - len(overlap), 0) if overlap else paragraph_start
            current_len = len("\n\n".join(current))
        else:
            if not current:
                current_start = paragraph_start
            current.append(paragraph)
            current_len = candidate_len
        offset = paragraph_start + len(paragraph)
    if current:
        chunk_text = "\n\n".join(current)
        chunks.append((current_start, current_start + len(chunk_text), chunk_text))
    return chunks


def _parse_markdown_chunks(
    markdown: str,
    slug: str,
    markdown_relative: str,
    *,
    max_chars: int,
    overlap_chars: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    section_path: list[str] = []
    current_page: int | None = None
    saw_page_marker = False
    section_buffers: list[tuple[list[str], int | None, str]] = []
    buffer_lines: list[str] = []

    def flush() -> None:
        nonlocal buffer_lines
        text = "\n".join(buffer_lines).strip()
        if text:
            section_buffers.append((list(section_path), current_page, text))
        buffer_lines = []

    for line in markdown.splitlines():
        page_match = PAGE_MARKER.match(line)
        if page_match:
            flush()
            current_page = int(next(group for group in page_match.groups() if group))
            saw_page_marker = True
            continue
        heading = HEADING.match(line)
        if heading:
            flush()
            level = len(heading.group(1))
            title = heading.group(2).strip()
            section_path = section_path[: level - 1]
            section_path.append(title)
            continue
        buffer_lines.append(line)
    flush()

    chunks: list[dict[str, Any]] = []
    for section, page, text in section_buffers:
        for char_start, char_end, chunk_text in _split_paragraph_chunks(text, max_chars, overlap_chars):
            chunk_index = len(chunks) + 1
            chunk = {
                "chunk_id": f"{slug}:c{chunk_index:04d}",
                "page": page,
                "section_path": section,
                "text": chunk_text,
                "char_start": char_start,
                "char_end": char_end,
                "source_locator": f"{markdown_relative}#{_slug_fragment(section, chunk_index)}",
                "support_scope": "source-text",
            }
            chunk["hash"] = _chunk_hash(chunk)
            chunks.append(chunk)
    if not saw_page_marker:
        warnings.append("page markers not found")
    return chunks, warnings


def build_paper_evidence_index(
    paper_root: Path,
    *,
    vault_path: Path | None = None,
    max_chars: int = 1200,
    overlap_chars: int = 150,
) -> dict[str, Any]:
    paper_root = paper_root.resolve()
    slug = paper_root.name
    markdown_path = resolve_mineru_markdown_path(paper_root)
    if not markdown_path.exists():
        raise FileNotFoundError(f"missing MinerU Markdown: {markdown_path}")
    metadata = _load_metadata(paper_root)
    markdown_relative = resolved_mineru_markdown_relative_path(paper_root)
    chunks, warnings = _parse_markdown_chunks(
        markdown_path.read_text(encoding="utf-8"),
        slug,
        markdown_relative,
        max_chars=max_chars,
        overlap_chars=overlap_chars,
    )

    input_hashes = {"mineru_markdown": file_sha256(markdown_path)}
    metadata_path = paper_root / "metadata.json"
    if metadata_path.exists():
        input_hashes["metadata"] = file_sha256(metadata_path)

    now = utc_now()
    index = {
        "schema_version": "paper-source-paper-evidence-index-v1",
        "paper_slug": slug,
        "title": metadata.get("title") or slug,
        "doi": metadata.get("doi"),
        "arxiv_id": metadata.get("arxiv_id"),
        "created_at": now,
        "updated_at": now,
        "source_artifacts": {
            "metadata": "metadata.json",
            "paper_pdf": "paper.pdf",
            "mineru_markdown": markdown_relative,
            "mineru_tex": "mineru/paper.tex" if has_nonempty_mineru_tex(paper_root) else None,
            "mineru_manifest": "mineru/mineru-manifest.json",
            "images": "mineru/images",
        },
        "input_hashes": input_hashes,
        "chunking": {
            "max_chars": max_chars,
            "overlap_chars": overlap_chars,
            "section_aware": True,
        },
        "chunks": chunks,
        "warnings": warnings,
    }
    write_json_atomic(paper_root / "evidence-index.json", index)
    if vault_path is not None:
        refresh_vault_evidence_index(vault_path, index)
    return index


def refresh_vault_evidence_index(vault_path: Path, paper_index: dict[str, Any]) -> dict[str, Any]:
    vault_path = vault_path.resolve()
    aggregate_path = paper_source_meta_root(vault_path) / "evidence-index.json"
    try:
        aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        aggregate = {"schema_version": "paper-source-vault-evidence-index-v1", "papers": []}

    papers = [
        item
        for item in aggregate.get("papers", [])
        if isinstance(item, dict) and item.get("paper_slug") != paper_index.get("paper_slug")
    ]
    evidence_path = raw_paper_root(vault_path, str(paper_index["paper_slug"])) / "evidence-index.json"
    papers.append(
        {
            "paper_slug": paper_index.get("paper_slug"),
            "title": paper_index.get("title"),
            "doi": paper_index.get("doi"),
            "arxiv_id": paper_index.get("arxiv_id"),
            "evidence_index": vault_relative(vault_path, evidence_path),
            "chunk_count": len(paper_index.get("chunks") or []),
            "input_hashes": paper_index.get("input_hashes") or {},
            "updated_at": paper_index.get("updated_at"),
        }
    )
    papers.sort(key=lambda item: str(item.get("paper_slug") or ""))

    aggregate = {
        "schema_version": "paper-source-vault-evidence-index-v1",
        "updated_at": utc_now(),
        "papers": papers,
    }
    write_json_atomic(aggregate_path, aggregate)
    return aggregate
