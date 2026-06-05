from __future__ import annotations

import urllib.parse

from epi.schemas import canonical_key, slugify_title


def _pdf_url_score(url: str) -> tuple[int, int]:
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if host in {"doi.org", "dx.doi.org"}:
        return (3, 0)
    direct_pdf = path.endswith(".pdf") or path.endswith("/pdf") or "/pdf/" in path
    if direct_pdf:
        return (0, 0)
    if "pdf" in path:
        return (1, 0)
    return (2, 0)


def _pdf_urls_from_record(record: dict) -> list[str]:
    urls: list[str] = []

    def add(value: object) -> None:
        if not value:
            return
        text = str(value).strip()
        if text and text not in urls:
            urls.append(text)

    add(record.get("pdf_url"))
    for key in ("pdf_urls", "open_access_pdf_urls"):
        values = record.get(key)
        if isinstance(values, list):
            for value in values:
                add(value)
    raw_record = record.get("raw_record") if isinstance(record.get("raw_record"), dict) else {}
    add(raw_record.get("pdf_url"))
    return sorted(urls, key=_pdf_url_score)


def _record_source_name(record: dict) -> str:
    raw_record = record.get("raw_record") if isinstance(record.get("raw_record"), dict) else {}
    return str(record.get("source") or raw_record.get("source") or "unknown")


def _record_paper_id(record: dict) -> str | None:
    raw_record = record.get("raw_record") if isinstance(record.get("raw_record"), dict) else {}
    for key in ("paper_id", "id", "arxiv_id", "doi"):
        value = record.get(key) or raw_record.get(key)
        if value:
            return str(value)
    return None


def _add_alternate_source(current: dict, record: dict) -> None:
    source = _record_source_name(record)
    alternate = {"source": source}
    paper_id = _record_paper_id(record)
    if paper_id:
        alternate["paper_id"] = paper_id
    if alternate not in current["alternate_sources"]:
        current["alternate_sources"].append(alternate)
        current["alternate_sources"].sort(key=lambda item: (item.get("source") or "", item.get("paper_id") or ""))


def _add_alternate_pdf_urls(current: dict, record: dict) -> None:
    source = _record_source_name(record)
    urls = current["alternate_pdf_urls"]
    for url in _pdf_urls_from_record(record):
        alternate = {"source": source, "url": url}
        if alternate not in urls:
            urls.append(alternate)
    urls.sort(key=lambda item: _pdf_url_score(item["url"]))


def _merge_pdf_urls(current: dict, record: dict) -> None:
    urls = list(current.get("pdf_urls") or [])
    for url in _pdf_urls_from_record(record):
        if url not in urls:
            urls.append(url)
    urls.sort(key=_pdf_url_score)
    current["pdf_urls"] = urls
    current["pdf_url"] = urls[0] if urls else None


def normalize_candidates(raw_records: list[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for record in raw_records:
        key = canonical_key(record)
        record_pdf_urls = _pdf_urls_from_record(record)
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
                "pdf_url": record_pdf_urls[0] if record_pdf_urls else record.get("pdf_url"),
                "pdf_urls": record_pdf_urls,
                "code_url": record.get("code_url"),
                "citation_count": int(record.get("citation_count") or 0),
                "sources": [],
                "alternate_sources": [],
                "alternate_pdf_urls": [],
                "raw_records": [],
            },
        )
        source = str(record.get("source") or "unknown")
        if source not in current["sources"]:
            current["sources"].append(source)
        current["sources"].sort()
        _add_alternate_source(current, record)
        _add_alternate_pdf_urls(current, record)
        current["raw_records"].append(record)
        _merge_pdf_urls(current, record)
        if not current.get("code_url") and record.get("code_url"):
            current["code_url"] = record.get("code_url")
        current["citation_count"] = max(current["citation_count"], int(record.get("citation_count") or 0))
    return list(merged.values())
