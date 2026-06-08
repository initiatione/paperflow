from __future__ import annotations

import os
import re
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from epi.artifacts import file_sha256, json_sha256, quarantine_root, utc_now, write_json_atomic
from epi.paper_search_adapter import download_paper_pdf, read_paper_preview


PDF_MAGIC = b"%PDF-"
DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
OA_SOURCE_PRIORITY = {
    "arxiv": 0,
    "pmc": 1,
    "europepmc": 2,
    "core": 3,
    "openaire": 4,
    "biorxiv": 5,
    "medrxiv": 6,
    "iacr": 7,
    "doaj": 8,
    "base": 9,
    "zenodo": 10,
    "hal": 11,
    "semantic": 20,
    "pubmed": 21,
    "crossref": 22,
    "openalex": 23,
    "dblp": 24,
    "google_scholar": 25,
    "citeseerx": 26,
    "ssrn": 27,
    "unpaywall": 28,
}


def _metadata_from_candidate(candidate: dict) -> dict:
    return {
        "slug": candidate["slug"],
        "title": candidate.get("title", ""),
        "authors": candidate.get("authors", []),
        "year": candidate.get("year"),
        "venue": candidate.get("venue", ""),
        "doi": candidate.get("doi"),
        "pdf_url": candidate.get("pdf_url"),
        "pdf_urls": candidate.get("pdf_urls", []),
        "score": candidate.get("score"),
        "sources": candidate.get("sources", []),
        "arxiv_id": candidate.get("arxiv_id"),
        "raw_records": candidate.get("raw_records", []),
    }


def _source_priority(source: str) -> int:
    return OA_SOURCE_PRIORITY.get(source.strip().lower(), 100)


def _paper_search_use_scihub() -> bool:
    return os.environ.get("EPI_PAPER_SEARCH_MCP_USE_SCIHUB", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _candidate_download_identities(candidate: dict) -> list[tuple[str, str]]:
    identities: list[tuple[str, str]] = []

    def add(source: object, paper_id: object) -> None:
        source_text = str(source or "").strip().lower()
        paper_id_text = str(paper_id or "").strip()
        if not source_text or not paper_id_text:
            return
        identity = (source_text, paper_id_text)
        if identity not in identities:
            identities.append(identity)

    for record in candidate.get("raw_records") or []:
        if not isinstance(record, dict):
            continue
        raw_record = record.get("raw_record") if isinstance(record.get("raw_record"), dict) else {}
        source = str(raw_record.get("source") or record.get("source") or "").strip().lower()
        paper_id = raw_record.get("paper_id") or record.get("paper_id")
        if not paper_id and source == "arxiv":
            paper_id = record.get("arxiv_id") or candidate.get("arxiv_id")
        add(source, paper_id)
    sources = candidate.get("sources") or []
    if isinstance(sources, str):
        sources = [sources]
    normalized_sources = [str(source).strip().lower() for source in sources]
    if "arxiv" in normalized_sources and candidate.get("arxiv_id"):
        add("arxiv", candidate["arxiv_id"])
    return sorted(identities, key=lambda item: (_source_priority(item[0]), identities.index(item)))


def _candidate_download_identity(candidate: dict) -> tuple[str, str] | None:
    identities = _candidate_download_identities(candidate)
    if identities:
        return identities[0]
    return None


def _candidate_pdf_urls(candidate: dict) -> list[str]:
    urls: list[str] = []

    def add(value: object) -> None:
        if not value:
            return
        text = str(value).strip()
        if text and text not in urls:
            urls.append(text)

    add(candidate.get("pdf_url"))
    pdf_urls = candidate.get("pdf_urls")
    if isinstance(pdf_urls, str):
        add(pdf_urls)
    elif isinstance(pdf_urls, list):
        for url in pdf_urls:
            add(url)
    alternate_pdf_urls = candidate.get("alternate_pdf_urls")
    if isinstance(alternate_pdf_urls, str):
        add(alternate_pdf_urls)
    elif isinstance(alternate_pdf_urls, list):
        for item in alternate_pdf_urls:
            if isinstance(item, dict):
                add(item.get("url") or item.get("pdf_url"))
            else:
                add(item)
    for record in candidate.get("raw_records") or []:
        if not isinstance(record, dict):
            continue
        add(record.get("pdf_url"))
        raw_record = record.get("raw_record") if isinstance(record.get("raw_record"), dict) else {}
        add(raw_record.get("pdf_url"))
    return urls


def _candidate_doi(candidate: dict) -> str:
    return str(candidate.get("doi") or "").strip()


def _candidate_doi_url(candidate: dict) -> str | None:
    doi = _candidate_doi(candidate)
    if not doi:
        return None
    if doi.lower().startswith(("http://", "https://")):
        return doi
    return f"https://doi.org/{doi}"


def _candidate_manual_urls(candidate: dict) -> list[dict]:
    urls: list[dict] = []
    seen: set[str] = set()

    def add(kind: str, value: object) -> None:
        if not value:
            return
        text = str(value).strip()
        if not text or text in seen:
            return
        seen.add(text)
        urls.append({"kind": kind, "url": text})

    doi_url = _candidate_doi_url(candidate)
    if doi_url:
        add("doi", doi_url)
    for key in ("publisher_url", "landing_page_url", "article_url", "url"):
        add("publisher", candidate.get(key))
    for pdf_url in _candidate_pdf_urls(candidate):
        add("publisher_pdf", pdf_url)
    for record in candidate.get("raw_records") or []:
        if not isinstance(record, dict):
            continue
        for key in ("publisher_url", "landing_page_url", "article_url", "url"):
            add("publisher", record.get(key))
        raw_record = record.get("raw_record") if isinstance(record.get("raw_record"), dict) else {}
        for key in ("publisher_url", "landing_page_url", "article_url", "url"):
            add("publisher", raw_record.get(key))
    return urls


def _manual_download_context(candidate: dict) -> dict | None:
    doi = _candidate_doi(candidate)
    manual_urls = _candidate_manual_urls(candidate)
    if not doi and not manual_urls:
        return None
    return {
        "required": True,
        "title": str(candidate.get("title") or ""),
        "doi": doi or None,
        "doi_url": _candidate_doi_url(candidate),
        "candidate_manual_urls": manual_urls,
        "preferred_next_step": (
            "Download the PDF through your organization/institution from the DOI or publisher page, "
            "then provide the local PDF or a direct open-access PDF URL to EPI."
        ),
        "tmp_manual_pdf_dir": "_epi/tmp-manual-pdfs",
        "avoid_exhaustive_fallbacks": True,
    }


def _manual_download_failure_hint() -> str:
    return (
        "No direct open PDF was available; use the DOI/publisher link and download through "
        "your organization/institution, then provide a local PDF or direct open-access PDF URL."
    )


def _should_mark_manual_download(
    candidate: dict,
    failure_class: str,
    http_status: int | None,
    error_kind: str | None,
) -> bool:
    if not _manual_download_context(candidate):
        return False
    if error_kind == "manual-download-required":
        return True
    if error_kind == "no-url":
        return True
    if http_status in (401, 403):
        return True
    return failure_class == "access-denied"


def _classify_acquire_failure(http_status: int | None, error_kind: str | None = None) -> tuple[str, bool, str]:
    """Map an acquisition failure to (failure_class, retryable, recovery_hint).

    Gives the driving agent an actionable signal instead of a single opaque error
    string. The hint is advisory only; EPI never auto-retries or auto-switches
    sources on its own.
    """

    if error_kind == "no-url":
        return "no-url", False, "Candidate has no pdf_url; switch to a downloadable source or enrich metadata."
    if error_kind == "already-exists":
        return "already-exists", False, "PDF already exists; use --redo / redo-acquire to refetch."
    if error_kind == "empty-pdf":
        return "empty-pdf", True, "Downloaded PDF was empty; retry or try an open-access/arXiv source."
    if error_kind == "not-pdf":
        return "not-pdf", True, "Downloaded URL was not a PDF; use the publisher PDF link, arXiv, or an open-access source."
    if error_kind == "manual-download-required":
        return "manual-download-required", False, _manual_download_failure_hint()
    if http_status is not None:
        if http_status in (401, 403):
            return "access-denied", False, "Source denied access; try arXiv/open-access source or a mirror."
        if http_status in (404, 410):
            return "not-found", False, "PDF URL is dead; switch source or skip this candidate."
        if http_status in (408, 429):
            return "rate-limited", True, "Rate limited; slow down and retry later."
        if 500 <= http_status <= 599:
            return "server-error", True, "Upstream temporary failure; retry later or try another source."
        return "http-error", False, f"HTTP {http_status}; verify the source URL."
    if error_kind in ("network", "timeout"):
        return "network", True, "Network/timeout error; retry or try another source."
    return "unknown", False, "Unknown acquisition failure; check the source URL and network."


class _PdfUrlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key.lower(): value for key, value in attrs if key and value}
        tag_name = tag.lower()
        if tag_name == "meta":
            name = str(attributes.get("name") or attributes.get("property") or "").strip().lower()
            content = attributes.get("content")
            if name == "citation_pdf_url" and content:
                self.urls.append(content.strip())
            return
        if tag_name not in {"a", "link"}:
            return
        href = attributes.get("href")
        if not href:
            return
        rel = str(attributes.get("rel") or "").lower()
        content_type = str(attributes.get("type") or "").lower()
        parsed = urllib.parse.urlparse(href)
        path = parsed.path.lower()
        if "pdf" in rel or content_type == "application/pdf" or path.endswith(".pdf") or path.endswith("/pdf"):
            self.urls.append(href.strip())


def _downloaded_file_is_pdf(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            preview = handle.read(1024)
    except OSError:
        return False
    return preview.lstrip().startswith(PDF_MAGIC)


def _normalize_doi(value: object) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^https?://(dx\.)?doi\.org/", "", text, flags=re.IGNORECASE)
    text = text.strip().strip(".")
    return text.lower()


def _normalize_title_tokens(value: object) -> set[str]:
    text = str(value or "").lower()
    return {token for token in re.findall(r"[a-z0-9]+", text) if len(token) >= 3}


def _pdf_identity_preview(path: Path) -> str:
    try:
        data = path.read_bytes()[:262144]
    except OSError:
        return ""
    return data.decode("latin-1", errors="ignore")


def _extract_pdf_identity(path: Path) -> dict:
    text = _pdf_identity_preview(path)
    dois = []
    for match in DOI_PATTERN.findall(text):
        normalized = _normalize_doi(match)
        if normalized and normalized not in dois:
            dois.append(normalized)
    title = None
    title_match = re.search(r"(?im)^\s*Title\s*:\s*(.+?)\s*$", text)
    if title_match:
        title = " ".join(title_match.group(1).split())
    return {
        "dois": dois,
        "title": title,
        "text_preview_chars": min(len(text), 262144),
    }


def _check_pdf_identity(candidate: dict, pdf_path: Path) -> dict:
    extracted = _extract_pdf_identity(pdf_path)
    candidate_doi = _normalize_doi(candidate.get("doi"))
    extracted_dois = extracted.get("dois") or []
    if candidate_doi and extracted_dois:
        if candidate_doi in extracted_dois:
            return {
                "status": "passed",
                "reason": "doi_match",
                "candidate_doi": candidate_doi,
                "extracted": extracted,
            }
        return {
            "status": "failed",
            "reason": "doi_mismatch",
            "candidate_doi": candidate_doi,
            "extracted": extracted,
        }

    candidate_title_tokens = _normalize_title_tokens(candidate.get("title"))
    extracted_title_tokens = _normalize_title_tokens(extracted.get("title"))
    if candidate_title_tokens and extracted_title_tokens:
        overlap = len(candidate_title_tokens & extracted_title_tokens)
        score = overlap / max(1, len(candidate_title_tokens))
        if score >= 0.6:
            return {
                "status": "passed",
                "reason": "title_match",
                "title_match_score": round(score, 4),
                "extracted": extracted,
            }
        return {
            "status": "failed",
            "reason": "title_mismatch",
            "title_match_score": round(score, 4),
            "extracted": extracted,
        }

    return {
        "status": "inconclusive",
        "reason": "insufficient_pdf_identity_text",
        "extracted": extracted,
    }


def _quarantine_identity_mismatch(
    paper_root: Path,
    candidate: dict,
    temp_pdf: Path,
    identity_check: dict,
    *,
    mode: str,
    started_at: str,
    candidate_metadata_hash: str,
    http_status: int | None = None,
    acquire_attempts: list[dict] | None = None,
    extra_record_fields: dict | None = None,
) -> dict:
    paper_root.mkdir(parents=True, exist_ok=True)
    write_json_atomic(paper_root / "metadata.json", _metadata_from_candidate(candidate))
    vault_root = paper_root.parents[2]
    slug = str(candidate.get("slug") or paper_root.name)
    quarantine_dir = quarantine_root(vault_root) / "papers" / slug
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    quarantine_pdf = quarantine_dir / "paper.pdf"
    os.replace(temp_pdf, quarantine_pdf)
    identity_record = {
        **identity_check,
        "candidate_title": str(candidate.get("title") or ""),
        "candidate_doi": _normalize_doi(candidate.get("doi")),
        "quarantine_path": str(quarantine_pdf),
        "checked_at": utc_now(),
    }
    write_json_atomic(paper_root / "identity-check.json", identity_record)
    record = {
        "stage": "acquire",
        "mode": mode,
        "status": "failed",
        "started_at": started_at,
        "finished_at": utc_now(),
        "retrieved_at": utc_now(),
        "exit_status": 1,
        "pdf_url": candidate.get("pdf_url"),
        "candidate_pdf_urls": _candidate_pdf_urls(candidate),
        "http_status": http_status,
        "failure_class": "identity-mismatch",
        "retryable": False,
        "recovery_hint": "Downloaded PDF identity did not match the candidate DOI/title; verify the source URL or provide the correct PDF.",
        "output_path": str(paper_root / "paper.pdf"),
        "quarantine_path": str(quarantine_pdf),
        "error": f"downloaded PDF identity mismatch: {identity_check.get('reason')}",
        "identity_check": identity_record,
        "acquire_attempts": acquire_attempts or [],
        "input_artifact_hashes": {
            "candidate_metadata": candidate_metadata_hash,
        },
        "output_artifact_hashes": {
            "metadata.json": file_sha256(paper_root / "metadata.json"),
            "identity-check.json": file_sha256(paper_root / "identity-check.json"),
            "quarantine/paper.pdf": file_sha256(quarantine_pdf),
        },
    }
    if extra_record_fields:
        for key, value in extra_record_fields.items():
            if value is not None:
                record[key] = value
    write_json_atomic(paper_root / "acquire-record.json", record)
    return record


def _extract_pdf_url_from_landing_page(page_url: str, body: bytes, content_type: str | None) -> str | None:
    preview = body[:256].lstrip().lower()
    looks_like_html = preview.startswith((b"<html", b"<!doctype")) or b"<html" in preview
    if content_type and "html" not in content_type.lower() and not looks_like_html:
        return None
    try:
        text = body[:65536].decode("utf-8", errors="ignore")
    except Exception:
        return None
    parser = _PdfUrlParser()
    parser.feed(text)
    for url in parser.urls:
        resolved = urllib.parse.urljoin(page_url, url)
        parsed = urllib.parse.urlparse(resolved)
        if parsed.scheme in {"http", "https"}:
            return resolved
    return None


def _download_url_to_temp(url: str, temp_pdf: Path, timeout_seconds: int) -> tuple[int | None, str | None]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; EPI/0.1; +https://github.com/initiatione/paper-search)",
            "Accept": "application/pdf,text/html;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        http_status = getattr(response, "status", None) or response.getcode()
        content_type = response.headers.get("content-type")
        with temp_pdf.open("wb") as handle:
            shutil.copyfileobj(response, handle)
    return http_status, content_type


def _write_failed_acquire_record(
    paper_root: Path,
    candidate: dict,
    *,
    mode: str,
    error: str,
    started_at: str,
    candidate_metadata_hash: str,
    http_status: int | None = None,
    error_kind: str | None = None,
    acquire_attempts: list[dict] | None = None,
    extra_record_fields: dict | None = None,
) -> dict:
    paper_root.mkdir(parents=True, exist_ok=True)
    write_json_atomic(paper_root / "metadata.json", _metadata_from_candidate(candidate))
    failure_class, retryable, recovery_hint = _classify_acquire_failure(http_status, error_kind)
    manual_download = _manual_download_context(candidate)
    manual_download_required = _should_mark_manual_download(candidate, failure_class, http_status, error_kind)
    if manual_download_required:
        failure_class = "manual-download-required"
        retryable = False
        recovery_hint = _manual_download_failure_hint()
    record = {
        "stage": "acquire",
        "mode": mode,
        "status": "failed",
        "started_at": started_at,
        "finished_at": utc_now(),
        "retrieved_at": utc_now(),
        "exit_status": 1,
        "pdf_url": candidate.get("pdf_url"),
        "candidate_pdf_urls": _candidate_pdf_urls(candidate),
        "http_status": http_status,
        "failure_class": failure_class,
        "retryable": retryable,
        "recovery_hint": recovery_hint,
        "output_path": str(paper_root / "paper.pdf"),
        "error": error,
        "acquire_attempts": acquire_attempts or [],
        "input_artifact_hashes": {
            "candidate_metadata": candidate_metadata_hash,
        },
        "output_artifact_hashes": {
            "metadata.json": file_sha256(paper_root / "metadata.json"),
        },
    }
    if manual_download_required and manual_download:
        record["manual_download"] = manual_download
    if extra_record_fields:
        for key, value in extra_record_fields.items():
            if value is not None:
                record[key] = value
    write_json_atomic(paper_root / "acquire-record.json", record)
    return record


def acquire_paper(candidate: dict, pdf_path: Path, paper_root: Path, *, redo: bool = False) -> dict:
    paper_root.mkdir(parents=True, exist_ok=True)
    target_pdf = paper_root / "paper.pdf"
    started_at = utc_now()
    metadata = _metadata_from_candidate(candidate)
    candidate_metadata_hash = json_sha256(metadata)
    if target_pdf.exists() and not redo:
        raise FileExistsError(f"raw PDF already exists: {target_pdf}")
    shutil.copyfile(pdf_path, target_pdf)
    size_bytes = target_pdf.stat().st_size
    if size_bytes <= 0:
        raise ValueError(f"acquired PDF is empty: {target_pdf}")

    acquire_record = {
        "stage": "acquire",
        "mode": "local-file",
        "status": "success",
        "started_at": started_at,
        "finished_at": utc_now(),
        "retrieved_at": utc_now(),
        "exit_status": 0,
        "source_path": str(pdf_path.resolve()),
        "pdf_url": candidate.get("pdf_url"),
        "output_path": str(target_pdf),
        "size_bytes": size_bytes,
    }
    write_json_atomic(paper_root / "metadata.json", metadata)
    acquire_record["input_artifact_hashes"] = {
        "candidate_metadata": candidate_metadata_hash,
        "source_pdf": file_sha256(pdf_path.resolve()),
    }
    acquire_record["output_artifact_hashes"] = {
        "paper.pdf": file_sha256(target_pdf),
        "metadata.json": file_sha256(paper_root / "metadata.json"),
    }
    write_json_atomic(paper_root / "acquire-record.json", acquire_record)
    return acquire_record


def acquire_paper_from_url(
    candidate: dict,
    paper_root: Path,
    *,
    timeout_seconds: int = 60,
    redo: bool = False,
) -> dict:
    paper_root.mkdir(parents=True, exist_ok=True)
    candidate_pdf_urls = _candidate_pdf_urls(candidate)
    pdf_url = candidate_pdf_urls[0] if candidate_pdf_urls else candidate.get("pdf_url")
    target_pdf = paper_root / "paper.pdf"
    started_at = utc_now()
    metadata = _metadata_from_candidate(candidate)
    candidate_metadata_hash = json_sha256(metadata)
    if target_pdf.exists() and not redo:
        return _write_failed_acquire_record(
            paper_root,
            candidate,
            mode="url",
            error=f"raw PDF already exists: {target_pdf}",
            started_at=started_at,
            candidate_metadata_hash=candidate_metadata_hash,
            error_kind="already-exists",
        )

    temp_pdf = target_pdf.with_suffix(".pdf.tmp")
    download_identity = _candidate_download_identity(candidate)
    if download_identity is not None:
        source, paper_id = download_identity
        use_scihub = _paper_search_use_scihub()
        scihub_base_url = os.environ.get("EPI_PAPER_SEARCH_MCP_SCIHUB_BASE_URL", "https://sci-hub.se")
        with tempfile.TemporaryDirectory(prefix="epi-paper-search-") as temp_dir:
            download_record = download_paper_pdf(
                source=source,
                paper_id=paper_id,
                doi=str(candidate.get("doi") or ""),
                title=str(candidate.get("title") or ""),
                use_scihub=use_scihub,
                scihub_base_url=scihub_base_url,
                stop_after_oa_fallback=not bool(pdf_url) and bool(_manual_download_context(candidate)),
                output_dir=Path(temp_dir),
                timeout_seconds=timeout_seconds,
            )
            if download_record["status"] == "success":
                download_mode = download_record.get("mode", "paper_search_cli_download")
                downloaded_pdf = Path(download_record["downloaded_pdf"])
                shutil.copyfile(downloaded_pdf, temp_pdf)
                size_bytes = temp_pdf.stat().st_size
                if size_bytes <= 0:
                    temp_pdf.unlink(missing_ok=True)
                    return _write_failed_acquire_record(
                        paper_root,
                        candidate,
                        mode=download_mode,
                        error=f"downloaded PDF is empty: {source}:{paper_id}",
                        started_at=started_at,
                        candidate_metadata_hash=candidate_metadata_hash,
                        error_kind="empty-pdf",
                    )
                if not _downloaded_file_is_pdf(temp_pdf):
                    temp_pdf.unlink(missing_ok=True)
                    return _write_failed_acquire_record(
                        paper_root,
                        candidate,
                        mode=download_mode,
                        error=f"downloaded file is not a PDF: {source}:{paper_id}",
                        started_at=started_at,
                        candidate_metadata_hash=candidate_metadata_hash,
                        error_kind="not-pdf",
                    )
                identity_check = _check_pdf_identity(candidate, temp_pdf)
                if identity_check.get("status") == "failed":
                    return _quarantine_identity_mismatch(
                        paper_root,
                        candidate,
                        temp_pdf,
                        identity_check,
                        mode=download_mode,
                        started_at=started_at,
                        candidate_metadata_hash=candidate_metadata_hash,
                        extra_record_fields={
                            "source": source,
                            "paper_id": paper_id,
                            "doi": str(candidate.get("doi") or ""),
                            "title": str(candidate.get("title") or ""),
                            "use_scihub": use_scihub,
                            "mcp_probe": download_record.get("mcp_probe"),
                            "mcp_server_probe": download_record.get("mcp_server_probe"),
                            "upstream": download_record.get("upstream"),
                        },
                    )
                os.replace(temp_pdf, target_pdf)
                record = {
                    "stage": "acquire",
                    "mode": download_mode,
                    "status": "success",
                    "started_at": started_at,
                    "finished_at": utc_now(),
                    "retrieved_at": utc_now(),
                    "exit_status": 0,
                    "source": source,
                    "paper_id": paper_id,
                    "doi": str(candidate.get("doi") or ""),
                    "title": str(candidate.get("title") or ""),
                    "use_scihub": use_scihub,
                    "pdf_url": pdf_url,
                    "output_path": str(target_pdf),
                    "size_bytes": target_pdf.stat().st_size,
                    "mcp_probe": download_record.get("mcp_probe"),
                    "mcp_server_probe": download_record.get("mcp_server_probe"),
                    "upstream": download_record.get("upstream"),
                    "identity_check": identity_check,
                }
                upstream = record["upstream"] if isinstance(record.get("upstream"), dict) else {}
                if upstream.get("fallback_chain"):
                    record["fallback_chain"] = upstream.get("fallback_chain")
                elif download_mode == "paper_search_mcp_fallback_download":
                    record["fallback_chain"] = ["source-native", "openaire", "core", "europepmc", "pmc", "unpaywall"]
                preview_path = paper_root / "paper-search-read-preview.txt"
                try:
                    record["retrieval_preview"] = read_paper_preview(
                        source=source,
                        paper_id=paper_id,
                        output_path=preview_path,
                        save_dir=Path(temp_dir),
                        timeout_seconds=timeout_seconds,
                    )
                except Exception as exc:
                    record["retrieval_preview"] = {
                        "status": "failed",
                        "mode": "paper_search_read_preview",
                        "source": source,
                        "paper_id": paper_id,
                        "output_path": str(preview_path),
                        "authoritative": False,
                        "replaces_mineru": False,
                        "error": str(exc),
                    }
                write_json_atomic(paper_root / "metadata.json", metadata)
                record["input_artifact_hashes"] = {
                    "candidate_metadata": candidate_metadata_hash,
                }
                record["output_artifact_hashes"] = {
                    "paper.pdf": file_sha256(target_pdf),
                    "metadata.json": file_sha256(paper_root / "metadata.json"),
                }
                if preview_path.is_file():
                    record["output_artifact_hashes"]["paper-search-read-preview.txt"] = file_sha256(preview_path)
                write_json_atomic(paper_root / "acquire-record.json", record)
                return record
            if not pdf_url:
                return _write_failed_acquire_record(
                    paper_root,
                    candidate,
                    mode=download_record.get("mode", "paper_search_download"),
                    error=download_record.get("error", "paper-search fallback did not produce a PDF"),
                    started_at=started_at,
                    candidate_metadata_hash=candidate_metadata_hash,
                    error_kind=(
                        "manual-download-required" if _manual_download_context(candidate) else "no-url"
                    ),
                    extra_record_fields={
                        "source": source,
                        "paper_id": paper_id,
                        "doi": str(candidate.get("doi") or ""),
                        "title": str(candidate.get("title") or ""),
                        "use_scihub": use_scihub,
                        "mcp_probe": download_record.get("mcp_probe"),
                        "mcp_server_probe": download_record.get("mcp_server_probe"),
                        "upstream": download_record.get("upstream"),
                        "fallback_chain": (
                            download_record.get("upstream", {}).get("fallback_chain")
                            if isinstance(download_record.get("upstream"), dict)
                            else None
                        ),
                    },
                )

    if not pdf_url:
        return _write_failed_acquire_record(
            paper_root,
            candidate,
            mode="url",
            error="candidate pdf_url is required",
            started_at=started_at,
            candidate_metadata_hash=candidate_metadata_hash,
            error_kind="no-url",
        )

    http_status: int | None = None
    candidate_pdf_url = str(pdf_url)
    attempted_urls: set[str] = set()
    acquire_attempts: list[dict] = []
    last_error = "failed to download PDF"
    last_error_kind: str | None = "network"
    for initial_url in candidate_pdf_urls or [candidate_pdf_url]:
        current_url = str(initial_url)
        if current_url in attempted_urls:
            continue
        while True:
            attempted_urls.add(current_url)
            try:
                http_status, content_type = _download_url_to_temp(current_url, temp_pdf, timeout_seconds)
            except urllib.error.HTTPError as exc:
                temp_pdf.unlink(missing_ok=True)
                failure_class, _, _ = _classify_acquire_failure(exc.code)
                last_error = f"HTTP {exc.code} while downloading PDF: {current_url}"
                last_error_kind = None
                http_status = exc.code
                acquire_attempts.append(
                    {
                        "url": current_url,
                        "status": "failed",
                        "http_status": exc.code,
                        "failure_class": failure_class,
                        "error": last_error,
                    }
                )
                break
            except Exception as exc:
                temp_pdf.unlink(missing_ok=True)
                last_error = f"failed to download PDF: {exc}"
                last_error_kind = "network"
                acquire_attempts.append(
                    {
                        "url": current_url,
                        "status": "failed",
                        "http_status": http_status,
                        "failure_class": _classify_acquire_failure(http_status, last_error_kind)[0],
                        "error": last_error,
                    }
                )
                break
            size_bytes = temp_pdf.stat().st_size
            if size_bytes <= 0:
                temp_pdf.unlink(missing_ok=True)
                last_error = f"downloaded PDF is empty: {current_url}"
                last_error_kind = "empty-pdf"
                acquire_attempts.append(
                    {
                        "url": current_url,
                        "status": "failed",
                        "http_status": http_status,
                        "failure_class": _classify_acquire_failure(http_status, last_error_kind)[0],
                        "error": last_error,
                    }
                )
                break
            if _downloaded_file_is_pdf(temp_pdf):
                acquire_attempts.append(
                    {
                        "url": current_url,
                        "status": "success",
                        "http_status": http_status,
                    }
                )
                identity_check = _check_pdf_identity(candidate, temp_pdf)
                if identity_check.get("status") == "failed":
                    return _quarantine_identity_mismatch(
                        paper_root,
                        candidate,
                        temp_pdf,
                        identity_check,
                        mode="url",
                        started_at=started_at,
                        candidate_metadata_hash=candidate_metadata_hash,
                        http_status=http_status,
                        acquire_attempts=acquire_attempts,
                    )
                os.replace(temp_pdf, target_pdf)
                record = {
                    "stage": "acquire",
                    "mode": "url",
                    "status": "success",
                    "started_at": started_at,
                    "finished_at": utc_now(),
                    "retrieved_at": utc_now(),
                    "exit_status": 0,
                    "pdf_url": current_url,
                    "candidate_pdf_url": candidate_pdf_url,
                    "candidate_pdf_urls": candidate_pdf_urls,
                    "resolved_pdf_url": current_url,
                    "http_status": http_status,
                    "acquire_attempts": acquire_attempts,
                    "identity_check": identity_check,
                    "output_path": str(target_pdf),
                    "size_bytes": target_pdf.stat().st_size,
                }
                write_json_atomic(paper_root / "metadata.json", metadata)
                record["input_artifact_hashes"] = {
                    "candidate_metadata": candidate_metadata_hash,
                }
                record["output_artifact_hashes"] = {
                    "paper.pdf": file_sha256(target_pdf),
                    "metadata.json": file_sha256(paper_root / "metadata.json"),
                }
                write_json_atomic(paper_root / "acquire-record.json", record)
                return record
            body = temp_pdf.read_bytes()
            resolved_pdf_url = _extract_pdf_url_from_landing_page(current_url, body, content_type)
            temp_pdf.unlink(missing_ok=True)
            if resolved_pdf_url and resolved_pdf_url not in attempted_urls:
                acquire_attempts.append(
                    {
                        "url": current_url,
                        "status": "resolved",
                        "http_status": http_status,
                        "resolved_pdf_url": resolved_pdf_url,
                    }
                )
                current_url = resolved_pdf_url
                continue
            last_error = f"downloaded URL is not a PDF and no PDF link was found: {current_url}"
            last_error_kind = "not-pdf"
            acquire_attempts.append(
                {
                    "url": current_url,
                    "status": "failed",
                    "http_status": http_status,
                    "failure_class": _classify_acquire_failure(http_status, last_error_kind)[0],
                    "error": last_error,
                }
            )
            break
    return _write_failed_acquire_record(
        paper_root,
        candidate,
        mode="url",
        http_status=http_status,
        error=last_error,
        started_at=started_at,
        candidate_metadata_hash=candidate_metadata_hash,
        error_kind=last_error_kind,
        acquire_attempts=acquire_attempts,
    )
