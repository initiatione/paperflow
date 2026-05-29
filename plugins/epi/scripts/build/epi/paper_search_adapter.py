from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
from pathlib import Path


DEFAULT_SOURCES = ["arxiv", "semantic", "openalex", "crossref", "dblp"]
COMMAND_UNAVAILABLE = "paper-search command unavailable; install paper-search-mcp or configure EPI_PAPER_SEARCH_COMMAND"
PROBE_TIMEOUT_SECONDS = 60


def _resolve_command(command: str) -> str | None:
    command_path = Path(command)
    if command_path.exists():
        return str(command_path)
    return shutil.which(command)


def _command_args(resolved_command: str, args: list[str]) -> list[str]:
    if Path(resolved_command).suffix.lower() == ".ps1":
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", resolved_command, *args]
    return [resolved_command, *args]


def _run_command(resolved_command: str, args: list[str], timeout_seconds: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        _command_args(resolved_command, args),
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )


def probe_paper_search_mcp(command: str = "paper-search") -> dict:
    resolved = _resolve_command(command)
    if not resolved:
        return {"available": False, "command": command, "error": "command_not_found"}
    try:
        version_probe = _run_command(resolved, ["--version"], timeout_seconds=PROBE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return {"available": False, "command": resolved, "error": "probe_timeout"}
    if version_probe.returncode == 0:
        return {
            "available": True,
            "command": resolved,
            "returncode": version_probe.returncode,
            "stdout": version_probe.stdout.strip(),
            "stderr": version_probe.stderr.strip(),
        }
    try:
        sources_probe = _run_command(resolved, ["sources"], timeout_seconds=PROBE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return {
            "available": False,
            "command": resolved,
            "returncode": version_probe.returncode,
            "stdout": version_probe.stdout.strip(),
            "stderr": version_probe.stderr.strip(),
            "error": "probe_timeout",
        }
    return {
        "available": sources_probe.returncode == 0,
        "command": resolved,
        "returncode": sources_probe.returncode,
        "stdout": version_probe.stdout.strip(),
        "stderr": version_probe.stderr.strip(),
        "sources_probe": {
            "returncode": sources_probe.returncode,
            "stdout": sources_probe.stdout.strip(),
            "stderr": sources_probe.stderr.strip(),
        },
    }


def _split_authors(authors: object) -> list[str]:
    if isinstance(authors, list):
        return [str(author).strip() for author in authors if str(author).strip()]
    if not authors:
        return []
    return [part.strip() for part in str(authors).replace(",", ";").split(";") if part.strip()]


def _parse_extra(extra: object) -> dict:
    if isinstance(extra, dict):
        return extra
    if not extra:
        return {}
    if isinstance(extra, str):
        for parser in (json.loads, ast.literal_eval):
            try:
                parsed = parser(extra)
            except (SyntaxError, ValueError, TypeError, json.JSONDecodeError):
                continue
            if isinstance(parsed, dict):
                return parsed
    return {}


def _extract_year(record: dict, extra: dict) -> int | None:
    for key in ("year", "published_year"):
        if record.get(key):
            return int(record[key])
    for key in ("published_date", "updated_date", "publication_date", "date"):
        value = record.get(key) or extra.get(key)
        if value:
            text = str(value)
            if len(text) >= 4 and text[:4].isdigit():
                return int(text[:4])
    return None


def _extract_arxiv_id(record: dict) -> str | None:
    if record.get("arxiv_id"):
        return str(record["arxiv_id"])
    source = str(record.get("source") or "").lower()
    paper_id = record.get("paper_id")
    if source == "arxiv" and paper_id:
        return str(paper_id)
    return None


def _citation_count(record: dict) -> int:
    for key in ("citation_count", "citations"):
        if record.get(key) is not None:
            return int(record.get(key) or 0)
    return 0


def _normalize_paper_search_record(record: dict) -> dict:
    extra = _parse_extra(record.get("extra"))
    return {
        "source": record.get("source") or "paper-search",
        "title": record.get("title") or "",
        "authors": _split_authors(record.get("authors")),
        "year": _extract_year(record, extra),
        "venue": record.get("venue") or extra.get("venue") or extra.get("publication_venue") or "",
        "abstract": record.get("abstract") or "",
        "doi": record.get("doi") or None,
        "arxiv_id": _extract_arxiv_id(record),
        "pdf_url": record.get("pdf_url") or None,
        "url": record.get("url") or None,
        "code_url": record.get("code_url") or extra.get("code_url") or extra.get("code") or None,
        "citation_count": _citation_count(record),
        "raw_record": record,
    }


def _write_raw_response(raw_response_path: Path | None, payload: dict) -> str | None:
    if raw_response_path is None:
        return None
    raw_response_path.parent.mkdir(parents=True, exist_ok=True)
    raw_response_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(raw_response_path)


def discover(
    query: str,
    max_results: int,
    fixture_path: Path | None = None,
    command: str | None = None,
    sources: list[str] | None = None,
    raw_response_path: Path | None = None,
    timeout_seconds: int = 90,
) -> dict:
    if fixture_path:
        records = json.loads(fixture_path.read_text(encoding="utf-8"))
        return {
            "query": query,
            "max_results": max_results,
            "source_mode": "fixture",
            "mcp_probe": {"available": True, "command": "fixture"},
            "records": records[:max_results],
        }
    selected_command = command or os.environ.get("EPI_PAPER_SEARCH_COMMAND") or "paper-search"
    selected_sources = sources or DEFAULT_SOURCES
    probe = probe_paper_search_mcp(selected_command)
    if not probe["available"]:
        return {
            "query": query,
            "max_results": max_results,
            "source_mode": "paper_search_cli",
            "mcp_probe": probe,
            "records": [],
            "error": COMMAND_UNAVAILABLE,
        }
    resolved_command = probe["command"]
    args = ["search", query, "-n", str(max_results), "-s", ",".join(selected_sources)]
    result = _run_command(resolved_command, args, timeout_seconds=timeout_seconds)
    if result.returncode != 0:
        raw_path = _write_raw_response(
            raw_response_path,
            {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            },
        )
        return {
            "query": query,
            "max_results": max_results,
            "source_mode": "paper_search_cli",
            "mcp_probe": probe,
            "raw_response_path": raw_path,
            "records": [],
            "error": "paper-search search failed",
            "upstream": {
                "package": "paper-search-mcp",
                "cli_command": resolved_command,
                "version_probe": probe,
                "sources_requested": selected_sources,
                "returncode": result.returncode,
                "stderr": result.stderr.strip(),
            },
        }
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raw_path = _write_raw_response(
            raw_response_path,
            {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            },
        )
        return {
            "query": query,
            "max_results": max_results,
            "source_mode": "paper_search_cli",
            "mcp_probe": probe,
            "raw_response_path": raw_path,
            "records": [],
            "error": f"paper-search search returned invalid JSON: {exc}",
        }
    raw_path = _write_raw_response(raw_response_path, payload)
    return {
        "query": query,
        "max_results": max_results,
        "source_mode": "paper_search_cli",
        "mcp_probe": probe,
        "raw_response_path": raw_path,
        "records": [_normalize_paper_search_record(record) for record in payload.get("papers", [])][:max_results],
        "upstream": {
            "package": "paper-search-mcp",
            "cli_command": resolved_command,
            "version_probe": probe,
            "query": payload.get("query", query),
            "sources_requested": selected_sources,
            "sources_used": payload.get("sources_used", []),
            "source_results": payload.get("source_results", {}),
            "errors": payload.get("errors", {}),
            "total": payload.get("total"),
        },
    }


def download_paper_pdf(
    *,
    source: str,
    paper_id: str,
    output_dir: Path,
    command: str | None = None,
    timeout_seconds: int = 120,
) -> dict:
    selected_command = command or os.environ.get("EPI_PAPER_SEARCH_COMMAND") or "paper-search"
    probe = probe_paper_search_mcp(selected_command)
    if not probe["available"]:
        return {
            "status": "failed",
            "mode": "paper_search_cli_download",
            "source": source,
            "paper_id": paper_id,
            "mcp_probe": probe,
            "error": COMMAND_UNAVAILABLE,
        }
    output_dir.mkdir(parents=True, exist_ok=True)
    resolved_command = probe["command"]
    args = ["download", source, paper_id, "--save-path", str(output_dir)]
    result = _run_command(resolved_command, args, timeout_seconds=timeout_seconds)
    pdf_paths = sorted(
        path
        for path in output_dir.rglob("*")
        if path.is_file() and path.suffix.lower() == ".pdf" and path.stat().st_size > 0
    )
    if result.returncode != 0:
        return {
            "status": "failed",
            "mode": "paper_search_cli_download",
            "source": source,
            "paper_id": paper_id,
            "mcp_probe": probe,
            "upstream": {
                "package": "paper-search-mcp",
                "cli_command": resolved_command,
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            },
            "error": "paper-search download failed",
        }
    if not pdf_paths:
        return {
            "status": "failed",
            "mode": "paper_search_cli_download",
            "source": source,
            "paper_id": paper_id,
            "mcp_probe": probe,
            "upstream": {
                "package": "paper-search-mcp",
                "cli_command": resolved_command,
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
            },
            "error": "paper-search download produced no PDF",
        }
    return {
        "status": "success",
        "mode": "paper_search_cli_download",
        "source": source,
        "paper_id": paper_id,
        "mcp_probe": probe,
        "downloaded_pdf": str(pdf_paths[0]),
        "upstream": {
            "package": "paper-search-mcp",
            "cli_command": resolved_command,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        },
    }
