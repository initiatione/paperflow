from __future__ import annotations

import os
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from epi.artifacts import file_sha256, json_sha256, utc_now, write_json_atomic
from epi.paper_search_adapter import download_paper_pdf


PDF_MAGIC = b"%PDF-"


def _metadata_from_candidate(candidate: dict) -> dict:
    return {
        "slug": candidate["slug"],
        "title": candidate.get("title", ""),
        "authors": candidate.get("authors", []),
        "year": candidate.get("year"),
        "venue": candidate.get("venue", ""),
        "doi": candidate.get("doi"),
        "pdf_url": candidate.get("pdf_url"),
        "score": candidate.get("score"),
        "sources": candidate.get("sources", []),
        "arxiv_id": candidate.get("arxiv_id"),
        "raw_records": candidate.get("raw_records", []),
    }


def _candidate_download_identity(candidate: dict) -> tuple[str, str] | None:
    for record in candidate.get("raw_records") or []:
        if not isinstance(record, dict):
            continue
        raw_record = record.get("raw_record") if isinstance(record.get("raw_record"), dict) else {}
        source = str(raw_record.get("source") or record.get("source") or "").strip().lower()
        paper_id = raw_record.get("paper_id") or record.get("paper_id")
        if not paper_id and source == "arxiv":
            paper_id = record.get("arxiv_id") or candidate.get("arxiv_id")
        if source and paper_id:
            return source, str(paper_id)
    sources = candidate.get("sources") or []
    if isinstance(sources, str):
        sources = [sources]
    normalized_sources = [str(source).strip().lower() for source in sources]
    if "arxiv" in normalized_sources and candidate.get("arxiv_id"):
        return "arxiv", str(candidate["arxiv_id"])
    return None


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
    request = urllib.request.Request(url, headers={"User-Agent": "EPI/0.1"})
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
) -> dict:
    paper_root.mkdir(parents=True, exist_ok=True)
    write_json_atomic(paper_root / "metadata.json", _metadata_from_candidate(candidate))
    failure_class, retryable, recovery_hint = _classify_acquire_failure(http_status, error_kind)
    record = {
        "stage": "acquire",
        "mode": mode,
        "status": "failed",
        "started_at": started_at,
        "finished_at": utc_now(),
        "retrieved_at": utc_now(),
        "exit_status": 1,
        "pdf_url": candidate.get("pdf_url"),
        "http_status": http_status,
        "failure_class": failure_class,
        "retryable": retryable,
        "recovery_hint": recovery_hint,
        "output_path": str(paper_root / "paper.pdf"),
        "error": error,
        "input_artifact_hashes": {
            "candidate_metadata": candidate_metadata_hash,
        },
        "output_artifact_hashes": {
            "metadata.json": file_sha256(paper_root / "metadata.json"),
        },
    }
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
    pdf_url = candidate.get("pdf_url")
    target_pdf = paper_root / "paper.pdf"
    started_at = utc_now()
    metadata = _metadata_from_candidate(candidate)
    candidate_metadata_hash = json_sha256(metadata)
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
        with tempfile.TemporaryDirectory(prefix="epi-paper-search-") as temp_dir:
            download_record = download_paper_pdf(
                source=source,
                paper_id=paper_id,
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
                    "pdf_url": pdf_url,
                    "output_path": str(target_pdf),
                    "size_bytes": target_pdf.stat().st_size,
                    "mcp_probe": download_record.get("mcp_probe"),
                    "upstream": download_record.get("upstream"),
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

    http_status: int | None = None
    candidate_pdf_url = str(pdf_url)
    current_url = candidate_pdf_url
    attempted_urls: set[str] = set()
    try:
        while True:
            attempted_urls.add(current_url)
            http_status, content_type = _download_url_to_temp(current_url, temp_pdf, timeout_seconds)
            size_bytes = temp_pdf.stat().st_size
            if size_bytes <= 0:
                temp_pdf.unlink(missing_ok=True)
                return _write_failed_acquire_record(
                    paper_root,
                    candidate,
                    mode="url",
                    http_status=http_status,
                    error=f"downloaded PDF is empty: {current_url}",
                    started_at=started_at,
                    candidate_metadata_hash=candidate_metadata_hash,
                    error_kind="empty-pdf",
                )
            if _downloaded_file_is_pdf(temp_pdf):
                break
            body = temp_pdf.read_bytes()
            resolved_pdf_url = _extract_pdf_url_from_landing_page(current_url, body, content_type)
            temp_pdf.unlink(missing_ok=True)
            if resolved_pdf_url and resolved_pdf_url not in attempted_urls:
                current_url = resolved_pdf_url
                continue
            return _write_failed_acquire_record(
                paper_root,
                candidate,
                mode="url",
                http_status=http_status,
                error=f"downloaded URL is not a PDF and no PDF link was found: {current_url}",
                started_at=started_at,
                candidate_metadata_hash=candidate_metadata_hash,
                error_kind="not-pdf",
            )
        os.replace(temp_pdf, target_pdf)
    except urllib.error.HTTPError as exc:
        temp_pdf.unlink(missing_ok=True)
        return _write_failed_acquire_record(
            paper_root,
            candidate,
            mode="url",
            http_status=exc.code,
            error=f"HTTP {exc.code} while downloading PDF: {current_url}",
            started_at=started_at,
            candidate_metadata_hash=candidate_metadata_hash,
        )
    except Exception as exc:
        temp_pdf.unlink(missing_ok=True)
        return _write_failed_acquire_record(
            paper_root,
            candidate,
            mode="url",
            http_status=http_status,
            error=f"failed to download PDF: {exc}",
            started_at=started_at,
            candidate_metadata_hash=candidate_metadata_hash,
            error_kind="network",
        )

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
        "resolved_pdf_url": current_url,
        "http_status": http_status,
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
