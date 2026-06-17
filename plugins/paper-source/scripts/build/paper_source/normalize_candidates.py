from __future__ import annotations

import re
import urllib.parse

from paper_source.schemas import canonical_key, slugify_title

DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[^\s\"'<>]+", re.IGNORECASE)
ARXIV_ID_PATTERN = re.compile(r"(?i)(?:arxiv:\s*|arxiv\.org/(?:abs|pdf)/)?(\d{4}\.\d{4,5}(?:v\d+)?)")
REPOSITORY_URL_PATTERN = re.compile(
    r"https?://(?:www\.)?(?:github\.com|gitlab\.com|bitbucket\.org)/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?",
    re.IGNORECASE,
)
DOI_KEY_ORDER = ["doi", "DOI"]
URL_KEY_ORDER = [
    "url",
    "URL",
    "link",
    "landing_page_url",
    "publisher_url",
    "pdf_url",
    "paper_url",
    "canonical_url",
    "source_url",
]
TEXT_KEY_ORDER = ["abstract", "summary", "snippet", "content", "description"]
IDENTITY_KEY_ORDER = ["arxiv_id", "paper_id", "id"]


def _strip_terminal_punctuation(value: str) -> str:
    return value.strip().strip(".,;:)]}>")


def _clean_doi(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^doi:\s*", "", text, flags=re.IGNORECASE)
    match = DOI_PATTERN.search(text)
    if match:
        return _strip_terminal_punctuation(match.group(0))
    if text.lower().startswith("10."):
        return _strip_terminal_punctuation(text)
    return None


def _arxiv_base_id(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    match = ARXIV_ID_PATTERN.search(text)
    if not match:
        return None
    return re.sub(r"v\d+$", "", match.group(1), flags=re.IGNORECASE)


def _arxiv_doi(value: object) -> str | None:
    base_id = _arxiv_base_id(value)
    if not base_id:
        return None
    return f"10.48550/arXiv.{base_id}"


def _iter_known_metadata_values(record: dict) -> list[tuple[str, object]]:
    values: list[tuple[str, object]] = []
    for key in DOI_KEY_ORDER + URL_KEY_ORDER + TEXT_KEY_ORDER + IDENTITY_KEY_ORDER:
        if key in record:
            values.append((key, record.get(key)))
    raw_record = record.get("raw_record") if isinstance(record.get("raw_record"), dict) else {}
    for key in DOI_KEY_ORDER + URL_KEY_ORDER + TEXT_KEY_ORDER + IDENTITY_KEY_ORDER:
        if key in raw_record:
            values.append((f"raw_record.{key}", raw_record.get(key)))
    ids = raw_record.get("ids") if isinstance(raw_record.get("ids"), dict) else {}
    for key in DOI_KEY_ORDER + URL_KEY_ORDER + ["arxiv"]:
        if key in ids:
            values.append((f"raw_record.ids.{key}", ids.get(key)))
    for location_key in ("primary_location", "best_oa_location"):
        location = raw_record.get(location_key) if isinstance(raw_record.get(location_key), dict) else {}
        for key in URL_KEY_ORDER + ["id"]:
            if key in location:
                values.append((f"raw_record.{location_key}.{key}", location.get(key)))
    return values


def _doi_from_known_metadata(record: dict) -> tuple[str | None, str | None]:
    doi = _clean_doi(record.get("doi"))
    if doi:
        return doi, "provider_doi"
    for source, value in _iter_known_metadata_values(record):
        doi = _clean_doi(value)
        if doi:
            return doi, source
    for source, value in [
        ("arxiv_id", record.get("arxiv_id")),
        ("paper_id", record.get("paper_id")),
        ("id", record.get("id")),
    ]:
        doi = _arxiv_doi(value)
        if doi:
            return doi, f"arxiv_id:{source}"
    for source, value in _iter_known_metadata_values(record):
        doi = _arxiv_doi(value)
        if doi:
            return doi, f"arxiv_id:{source}"
    return None, None


def _repository_url_from_known_metadata(record: dict) -> tuple[str | None, str | None]:
    for key in ("code_url", "repository_url"):
        value = str(record.get(key) or "").strip()
        if value:
            return _strip_terminal_punctuation(value), key
    for source, value in _iter_known_metadata_values(record):
        text = str(value or "")
        match = REPOSITORY_URL_PATTERN.search(text)
        if match:
            return _strip_terminal_punctuation(match.group(0)), source
    return None, None


def _enrich_record_metadata(record: dict) -> dict:
    enriched = dict(record)
    doi, doi_source = _doi_from_known_metadata(enriched)
    if doi:
        enriched["doi"] = doi
        enriched.setdefault("doi_source", doi_source)
    code_url, code_source = _repository_url_from_known_metadata(enriched)
    if code_url and not enriched.get("code_url"):
        enriched["code_url"] = code_url
        enriched.setdefault("code_url_source", code_source)
    if not enriched.get("arxiv_id"):
        for source, value in _iter_known_metadata_values(enriched):
            arxiv_id = _arxiv_base_id(value)
            if arxiv_id:
                enriched["arxiv_id"] = arxiv_id
                enriched.setdefault("arxiv_id_source", source)
                break
    return enriched


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
    for raw_record in raw_records:
        record = _enrich_record_metadata(raw_record)
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
                "doi_source": record.get("doi_source"),
                "arxiv_id": record.get("arxiv_id"),
                "arxiv_id_source": record.get("arxiv_id_source"),
                "pdf_url": record_pdf_urls[0] if record_pdf_urls else record.get("pdf_url"),
                "pdf_urls": record_pdf_urls,
                "code_url": record.get("code_url"),
                "code_url_source": record.get("code_url_source"),
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
            current["code_url_source"] = record.get("code_url_source")
        if not current.get("doi") and record.get("doi"):
            current["doi"] = record.get("doi")
            current["doi_source"] = record.get("doi_source")
        record_citations = _record_citation_count(record)
        record_citation_source = _record_citation_source(record)
        if record_citation_source and (
            not current.get("citation_count_source") or record_citations > int(current.get("citation_count") or 0)
        ):
            current["citation_count"] = record_citations
            current["citation_count_source"] = record_citation_source
            current["citation_count_status"] = _citation_status(record_citation_source)
    return list(merged.values())
