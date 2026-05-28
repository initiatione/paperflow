from __future__ import annotations

import os
import shutil
import urllib.error
import urllib.request
from pathlib import Path

from epi.artifacts import file_sha256, json_sha256, utc_now, write_json_atomic


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
    }


def _write_failed_acquire_record(
    paper_root: Path,
    candidate: dict,
    *,
    mode: str,
    error: str,
    started_at: str,
    candidate_metadata_hash: str,
    http_status: int | None = None,
) -> dict:
    paper_root.mkdir(parents=True, exist_ok=True)
    write_json_atomic(paper_root / "metadata.json", _metadata_from_candidate(candidate))
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
        )
    if target_pdf.exists() and not redo:
        return _write_failed_acquire_record(
            paper_root,
            candidate,
            mode="url",
            error=f"raw PDF already exists: {target_pdf}",
            started_at=started_at,
            candidate_metadata_hash=candidate_metadata_hash,
        )

    temp_pdf = target_pdf.with_suffix(".pdf.tmp")
    http_status: int | None = None
    try:
        request = urllib.request.Request(pdf_url, headers={"User-Agent": "EPI/0.1"})
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            http_status = getattr(response, "status", None) or response.getcode()
            with temp_pdf.open("wb") as handle:
                shutil.copyfileobj(response, handle)
        size_bytes = temp_pdf.stat().st_size
        if size_bytes <= 0:
            temp_pdf.unlink(missing_ok=True)
            return _write_failed_acquire_record(
                paper_root,
                candidate,
                mode="url",
                http_status=http_status,
                error=f"downloaded PDF is empty: {pdf_url}",
                started_at=started_at,
                candidate_metadata_hash=candidate_metadata_hash,
            )
        os.replace(temp_pdf, target_pdf)
    except urllib.error.HTTPError as exc:
        temp_pdf.unlink(missing_ok=True)
        return _write_failed_acquire_record(
            paper_root,
            candidate,
            mode="url",
            http_status=exc.code,
            error=f"HTTP {exc.code} while downloading PDF: {pdf_url}",
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
        )

    record = {
        "stage": "acquire",
        "mode": "url",
        "status": "success",
        "started_at": started_at,
        "finished_at": utc_now(),
        "retrieved_at": utc_now(),
        "exit_status": 0,
        "pdf_url": pdf_url,
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
