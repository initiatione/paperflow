from __future__ import annotations

from epi.artifacts import utc_now


def _unique_text(values: list[object]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _pdf_urls(candidate: dict) -> list[str]:
    values: list[object] = [candidate.get("pdf_url")]
    raw_pdf_urls = candidate.get("pdf_urls")
    if isinstance(raw_pdf_urls, str):
        values.append(raw_pdf_urls)
    elif isinstance(raw_pdf_urls, list):
        values.extend(raw_pdf_urls)
    alternate_pdf_urls = candidate.get("alternate_pdf_urls")
    if isinstance(alternate_pdf_urls, str):
        values.append(alternate_pdf_urls)
    elif isinstance(alternate_pdf_urls, list):
        for item in alternate_pdf_urls:
            values.append(item.get("url") if isinstance(item, dict) else item)
    return _unique_text(values)


def _source_identities(candidate: dict) -> list[dict]:
    identities: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for record in candidate.get("raw_records") or []:
        if not isinstance(record, dict):
            continue
        raw_record = record.get("raw_record") if isinstance(record.get("raw_record"), dict) else {}
        source = str(raw_record.get("source") or record.get("source") or "").strip().lower()
        paper_id = raw_record.get("paper_id") or record.get("paper_id")
        if not paper_id and source == "arxiv":
            paper_id = record.get("arxiv_id") or candidate.get("arxiv_id")
        paper_id_text = str(paper_id or "").strip()
        if not source or not paper_id_text:
            continue
        key = (source, paper_id_text)
        if key in seen:
            continue
        seen.add(key)
        identities.append({"source": source, "paper_id": paper_id_text})
    arxiv_id = str(candidate.get("arxiv_id") or "").strip()
    if arxiv_id and ("arxiv", arxiv_id) not in seen:
        identities.append({"source": "arxiv", "paper_id": arxiv_id})
    return identities


def _doi_url(doi: object) -> str | None:
    text = str(doi or "").strip()
    if not text:
        return None
    if text.lower().startswith(("http://", "https://")):
        return text
    return f"https://doi.org/{text}"


def _manual_download(candidate: dict, pdf_urls: list[str]) -> dict:
    urls: list[dict] = []
    doi_url = _doi_url(candidate.get("doi"))
    if doi_url:
        urls.append({"kind": "doi", "url": doi_url})
    for url in pdf_urls:
        urls.append({"kind": "publisher_pdf", "url": url})
    return {
        "required": not bool(pdf_urls),
        "doi_url": doi_url,
        "candidate_manual_urls": urls,
        "preferred_next_step": (
            "Use DOI/publisher/open-access links to provide a local PDF or direct open-access PDF URL."
        ),
    }


def build_fetch_plan(ranked_candidates: list[dict]) -> dict:
    items = []
    for candidate in ranked_candidates:
        urls = _pdf_urls(candidate)
        items.append(
            {
                "slug": candidate.get("slug"),
                "title": candidate.get("title"),
                "doi": candidate.get("doi"),
                "arxiv_id": candidate.get("arxiv_id"),
                "candidate_pdf_urls": urls,
                "source_identities": _source_identities(candidate),
                "manual_download": _manual_download(candidate, urls),
                "recommended_order": [
                    "paper-search-mcp-download-with-fallback",
                    "source-native-download",
                    "direct-pdf-url",
                    "manual-download",
                ],
                "known_blockers": [],
            }
        )
    return {
        "schema_version": "epi-fetch-plan-v1",
        "created_at": utc_now(),
        "item_count": len(items),
        "items": items,
    }
