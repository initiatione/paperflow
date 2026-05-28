from __future__ import annotations

from epi.schemas import canonical_key, slugify_title


def normalize_candidates(raw_records: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for record in raw_records:
        key = canonical_key(record)
        current = merged.setdefault(
            key,
            {
                "id": key,
                "slug": slugify_title(str(record.get("title") or "untitled-paper")),
                "title": record.get("title") or "",
                "authors": record.get("authors") or [],
                "year": record.get("year"),
                "venue": record.get("venue") or "",
                "abstract": record.get("abstract") or "",
                "doi": record.get("doi"),
                "arxiv_id": record.get("arxiv_id"),
                "pdf_url": record.get("pdf_url"),
                "code_url": record.get("code_url"),
                "citation_count": int(record.get("citation_count") or 0),
                "sources": [],
                "raw_records": [],
            },
        )
        source = str(record.get("source") or "unknown")
        if source not in current["sources"]:
            current["sources"].append(source)
        current["sources"].sort()
        current["raw_records"].append(record)
        if not current.get("pdf_url") and record.get("pdf_url"):
            current["pdf_url"] = record.get("pdf_url")
        if not current.get("code_url") and record.get("code_url"):
            current["code_url"] = record.get("code_url")
        current["citation_count"] = max(current["citation_count"], int(record.get("citation_count") or 0))
    return list(merged.values())
