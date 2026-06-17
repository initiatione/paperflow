from __future__ import annotations

import urllib.parse

from paper_source.schemas import canonical_key, slugify_title


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


def _record_provider_name(record: dict) -> str:
    provider = str(record.get("provider") or "").strip()
    if provider:
        return provider
    source = _record_source_name(record)
    return "grok_search" if source == "grok_search" else "paper_search"


def _record_paper_id(record: dict) -> str | None:
    raw_record = record.get("raw_record") if isinstance(record.get("raw_record"), dict) else {}
    for key in ("paper_id", "id", "arxiv_id", "doi"):
        value = record.get(key) or raw_record.get(key)
        if value:
            return str(value)
    return None


def _record_has_citation_count(record: dict) -> bool:
    raw_record = record.get("raw_record") if isinstance(record.get("raw_record"), dict) else {}
    return (
        "citation_count" in record
        or "citations" in record
        or "citation_count" in raw_record
        or "citations" in raw_record
    )


def _record_citation_count(record: dict) -> int:
    raw_record = record.get("raw_record") if isinstance(record.get("raw_record"), dict) else {}
    value = None
    for key in ("citation_count", "citations"):
        if record.get(key) is not None:
            value = record.get(key)
            break
        if raw_record.get(key) is not None:
            value = raw_record.get(key)
            break
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _record_citation_source(record: dict) -> str | None:
    if not _record_has_citation_count(record):
        return None
    return _record_source_name(record)


def _citation_status(source: str | None) -> str:
    if source:
        return "verified"
    return "unverified"


def _add_citation_source(current: dict, record: dict) -> None:
    source = _record_citation_source(record)
    if not source:
        return
    count = _record_citation_count(record)
    item = {"source": source, "count": count}
    if item not in current["citation_count_sources"]:
        current["citation_count_sources"].append(item)
        current["citation_count_sources"].sort(key=lambda value: (-int(value.get("count") or 0), value.get("source") or ""))


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


def _add_provider_provenance(current: dict, record: dict) -> None:
    provider = _record_provider_name(record)
    if provider not in current["provider_provenance"]:
        current["provider_provenance"].append(provider)
        current["provider_provenance"].sort()
    providers = set(current["provider_provenance"])
    if providers == {"paper_search"}:
        current["provenance_label"] = "paper_search_only"
    elif providers == {"grok_search"}:
        current["provenance_label"] = "grok_only_with_paper_search_anchor"
    elif {"paper_search", "grok_search"}.issubset(providers):
        current["provenance_label"] = "both_providers"
    else:
        current["provenance_label"] = "unknown_provider"


def _merge_pdf_urls(current: dict, record: dict) -> None:
    urls = list(current.get("pdf_urls") or [])
    for url in _pdf_urls_from_record(record):
        if url not in urls:
            urls.append(url)
    urls.sort(key=_pdf_url_score)
    current["pdf_urls"] = urls
    current["pdf_url"] = urls[0] if urls else None


def _fill_grok_supplemental_fields(current: dict, record: dict) -> None:
    if record.get("landing_page_url") and not current.get("landing_page_url"):
        current["landing_page_url"] = record.get("landing_page_url")
    if record.get("publisher_url") and not current.get("publisher_url"):
        current["publisher_url"] = record.get("publisher_url")
    if record.get("url") and not current.get("url"):
        current["url"] = record.get("url")


def _promote_paper_search_fields(current: dict, record: dict) -> None:
    if _record_provider_name(record) != "paper_search":
        return
    for field in ("title", "authors", "year", "venue", "abstract", "doi", "arxiv_id"):
        value = record.get(field)
        if value:
            current[field] = value


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
                "citation_count": _record_citation_count(record),
                "citation_count_source": _record_citation_source(record),
                "citation_count_status": _citation_status(_record_citation_source(record)),
                "citation_count_sources": [],
                "sources": [],
                "alternate_sources": [],
                "alternate_pdf_urls": [],
                "provider_provenance": [],
                "provenance_label": "unknown_provider",
                "landing_page_url": record.get("landing_page_url"),
                "publisher_url": record.get("publisher_url"),
                "url": record.get("url"),
                "raw_records": [],
            },
        )
        source = str(record.get("source") or "unknown")
        if source not in current["sources"]:
            current["sources"].append(source)
        current["sources"].sort()
        _add_alternate_source(current, record)
        _add_alternate_pdf_urls(current, record)
        _add_provider_provenance(current, record)
        _add_citation_source(current, record)
        current["raw_records"].append(record)
        _merge_pdf_urls(current, record)
        _fill_grok_supplemental_fields(current, record)
        _promote_paper_search_fields(current, record)
        if not current.get("code_url") and record.get("code_url"):
            current["code_url"] = record.get("code_url")
        record_citations = _record_citation_count(record)
        record_citation_source = _record_citation_source(record)
        if record_citation_source and (
            not current.get("citation_count_source") or record_citations > int(current.get("citation_count") or 0)
        ):
            current["citation_count"] = record_citations
            current["citation_count_source"] = record_citation_source
            current["citation_count_status"] = _citation_status(record_citation_source)
    return list(merged.values())
