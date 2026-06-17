from __future__ import annotations

import json
import os
import queue
import re
import shlex
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from paper_source.artifacts import write_json_atomic


MCP_PROTOCOL_VERSION = "2025-11-25"
SEARCH_TIMEOUT_SECONDS = 180
GROK_SEARCH_RESPONSE_FORMAT = "detailed"
DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[^\s\"'<>]+\b", re.IGNORECASE)
ARXIV_ID_PATTERN = re.compile(r"(?i)(?:arxiv:\s*|arxiv\.org/(?:abs|pdf)/)?(\d{4}\.\d{4,5}(?:v\d+)?)")
PAPER_HOST_HINTS = {
    "arxiv.org",
    "doi.org",
    "dx.doi.org",
    "ieeexplore.ieee.org",
    "dl.acm.org",
    "sciencedirect.com",
    "link.springer.com",
    "springer.com",
    "semanticscholar.org",
    "openalex.org",
    "crossref.org",
}


class GrokSearchMCPError(RuntimeError):
    def __init__(self, message: str, *, probe: dict | None = None, raw_response: dict | None = None) -> None:
        super().__init__(message)
        self.probe = probe or {}
        self.raw_response = raw_response or {}


def _split_command_line(command_line: str) -> list[str]:
    return [token.strip("\"'") for token in shlex.split(command_line, posix=False)]


def _resolve_command(command: str) -> str | None:
    command_path = Path(command)
    if command_path.exists():
        return str(command_path)
    return shutil.which(command)


def _command_args(resolved_command: str, args: list[str]) -> list[str]:
    if Path(resolved_command).suffix.lower() == ".ps1":
        return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", resolved_command, *args]
    return [resolved_command, *args]


def _mcp_command_args() -> tuple[list[str] | None, dict[str, Any]]:
    configured = os.environ.get("PAPER_SOURCE_GROK_SEARCH_MCP_COMMAND")
    if not configured:
        return None, {"available": False, "transport": "stdio", "error": "not_configured"}
    tokens = _split_command_line(configured)
    extra_args = os.environ.get("PAPER_SOURCE_GROK_SEARCH_MCP_ARGS")
    if extra_args:
        tokens.extend(_split_command_line(extra_args))
    if not tokens:
        return None, {"available": False, "transport": "stdio", "error": "not_configured"}
    resolved = _resolve_command(tokens[0])
    if not resolved:
        return None, {
            "available": False,
            "command": tokens[0],
            "args": tokens[1:],
            "transport": "stdio",
            "error": "command_not_found",
        }
    return _command_args(resolved, tokens[1:]), {
        "available": True,
        "command": resolved,
        "args": tokens[1:],
        "transport": "stdio",
    }


def _enqueue_stream_lines(stream, output: queue.Queue[str]) -> None:
    try:
        for line in iter(stream.readline, ""):
            output.put(line)
    finally:
        stream.close()


def _drain_queue(lines: queue.Queue[str]) -> list[str]:
    drained: list[str] = []
    while True:
        try:
            drained.append(lines.get_nowait())
        except queue.Empty:
            return drained


def _write_jsonrpc(process: subprocess.Popen[str], payload: dict[str, Any]) -> None:
    if process.stdin is None:
        raise GrokSearchMCPError("grok-search MCP stdin is unavailable")
    process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
    process.stdin.flush()


def _read_jsonrpc_response(
    *,
    process: subprocess.Popen[str],
    stdout_lines: queue.Queue[str],
    stderr_lines: queue.Queue[str],
    expected_id: int,
    deadline: float,
    probe: dict[str, Any],
) -> dict[str, Any]:
    ignored_stdout: list[str] = []
    while time.monotonic() < deadline:
        remaining = max(0.05, min(0.25, deadline - time.monotonic()))
        try:
            line = stdout_lines.get(timeout=remaining)
        except queue.Empty:
            if process.poll() is not None:
                raise GrokSearchMCPError(
                    "grok-search MCP server exited before response",
                    probe={**probe, "available": False, "error": "server_exited"},
                    raw_response={
                        "stdout": "".join(ignored_stdout + _drain_queue(stdout_lines)).strip(),
                        "stderr": "".join(_drain_queue(stderr_lines)).strip(),
                        "returncode": process.returncode,
                    },
                )
            continue
        stripped = line.strip()
        if not stripped:
            continue
        try:
            message = json.loads(stripped)
        except json.JSONDecodeError:
            ignored_stdout.append(line)
            continue
        if message.get("id") == expected_id:
            if "error" in message:
                error = message.get("error") or {}
                message_text = error.get("message") if isinstance(error, dict) else str(error)
                raise GrokSearchMCPError(
                    message_text or "grok-search MCP tool call failed",
                    probe={**probe, "available": False, "error": "jsonrpc_error"},
                    raw_response=message,
                )
            return message
    raise GrokSearchMCPError(
        "grok-search MCP tool call timed out",
        probe={**probe, "available": False, "error": "timeout"},
        raw_response={"stderr": "".join(_drain_queue(stderr_lines)).strip()},
    )


def _extract_mcp_text_content(result: dict[str, Any]) -> str:
    content = result.get("content") if isinstance(result, dict) else None
    if not isinstance(content, list):
        return ""
    parts = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(str(item.get("text") or ""))
    return "\n".join(part for part in parts if part)


def _extract_mcp_tool_payload(result: dict[str, Any]) -> dict[str, Any]:
    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        return structured
    text = _extract_mcp_text_content(result)
    if text:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {"content": text}
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    return {}


def _call_mcp_tool(tool_name: str, arguments: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    command_args, probe = _mcp_command_args()
    if not command_args:
        raise GrokSearchMCPError("grok-search MCP server is not configured", probe=probe)
    process = subprocess.Popen(
        command_args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    stdout_lines: queue.Queue[str] = queue.Queue()
    stderr_lines: queue.Queue[str] = queue.Queue()
    assert process.stdout is not None
    assert process.stderr is not None
    threading.Thread(target=_enqueue_stream_lines, args=(process.stdout, stdout_lines), daemon=True).start()
    threading.Thread(target=_enqueue_stream_lines, args=(process.stderr, stderr_lines), daemon=True).start()
    deadline = time.monotonic() + timeout_seconds
    try:
        _write_jsonrpc(
            process,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "paper-source", "version": "local"},
                },
            },
        )
        _read_jsonrpc_response(
            process=process,
            stdout_lines=stdout_lines,
            stderr_lines=stderr_lines,
            expected_id=1,
            deadline=deadline,
            probe=probe,
        )
        _write_jsonrpc(process, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        _write_jsonrpc(
            process,
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": tool_name, "arguments": arguments}},
        )
        raw = _read_jsonrpc_response(
            process=process,
            stdout_lines=stdout_lines,
            stderr_lines=stderr_lines,
            expected_id=2,
            deadline=deadline,
            probe=probe,
        )
        result = raw.get("result") if isinstance(raw.get("result"), dict) else {}
        return {"probe": probe, "payload": _extract_mcp_tool_payload(result), "raw_response": raw}
    finally:
        if process.stdin is not None:
            try:
                process.stdin.close()
            except OSError:
                pass
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()


def _first_match(pattern: re.Pattern[str], *values: object) -> str | None:
    for value in values:
        text = str(value or "")
        match = pattern.search(text)
        if match:
            return match.group(1) if match.groups() else match.group(0).strip(".,;")
    return None


def _source_url(source: dict[str, Any]) -> str:
    for key in ("url", "link", "landing_page_url", "pdf_url"):
        if source.get(key):
            return str(source[key]).strip()
    return ""


def _looks_like_paper(source: dict[str, Any]) -> tuple[bool, str | None]:
    title = str(source.get("title") or "").strip()
    url = _source_url(source)
    content = str(source.get("content") or source.get("snippet") or source.get("summary") or "")
    doi = _first_match(DOI_PATTERN, source.get("doi"), url, title, content)
    arxiv_id = _first_match(ARXIV_ID_PATTERN, source.get("arxiv_id"), url, title, content)
    if doi or arxiv_id:
        return True, None
    host = ""
    if "://" in url:
        host = url.split("://", 1)[1].split("/", 1)[0].lower()
    if host in PAPER_HOST_HINTS or any(host.endswith(f".{hint}") for hint in PAPER_HOST_HINTS):
        return True, None
    if source.get("authors") and (source.get("year") or source.get("published_date")) and title:
        return True, None
    return False, "missing_stable_paper_identity"


def _normalize_source(source: dict[str, Any], *, query: str, index: int) -> dict[str, Any]:
    title = str(source.get("title") or source.get("name") or "").strip()
    url = _source_url(source)
    content = str(source.get("content") or source.get("snippet") or source.get("summary") or "")
    doi = source.get("doi") or _first_match(DOI_PATTERN, url, title, content)
    arxiv_id = source.get("arxiv_id") or _first_match(ARXIV_ID_PATTERN, url, title, content)
    pdf_url = str(source.get("pdf_url") or "")
    lowered_url = url.lower()
    if not pdf_url and (lowered_url.endswith(".pdf") or "arxiv.org/pdf/" in lowered_url or "/pdf/" in lowered_url):
        pdf_url = url
    landing_page_url = str(source.get("landing_page_url") or source.get("publisher_url") or (url if url and not pdf_url else ""))
    authors = source.get("authors")
    if isinstance(authors, str):
        authors = [item.strip() for item in authors.split(",") if item.strip()]
    if not isinstance(authors, list):
        authors = []
    year = source.get("year")
    if year is None and source.get("published_date"):
        match = re.search(r"\b(19|20)\d{2}\b", str(source.get("published_date")))
        year = int(match.group(0)) if match else None
    return {
        "source": "grok_search",
        "provider": "grok_search",
        "title": title,
        "authors": authors,
        "year": year,
        "venue": source.get("venue") or source.get("publisher") or "",
        "abstract": content,
        "doi": doi,
        "arxiv_id": arxiv_id,
        "pdf_url": pdf_url or None,
        "landing_page_url": landing_page_url or None,
        "url": landing_page_url or pdf_url or url or None,
        "citation_count": int(source.get("citation_count") or source.get("citations") or 0),
        "query_variant": query,
        "query_variant_index": index,
        "raw_record": source,
    }


def normalize_grok_payload(payload: dict[str, Any], *, query: str, index: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sources = payload.get("sources")
    if not isinstance(sources, list):
        sources = []
    accepted: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        paper_like, reason = _looks_like_paper(source)
        if paper_like:
            accepted.append(_normalize_source(source, query=query, index=index))
        else:
            evidence.append(
                {
                    "provider": "grok_search",
                    "query": query,
                    "title": source.get("title") or source.get("name"),
                    "url": _source_url(source),
                    "reason": reason or "rejected",
                    "raw_record": source,
                }
            )
    return accepted, evidence


def discover_grok(
    *,
    queries: list[str],
    include_domains: list[str],
    raw_response_path: Path,
    evidence_path: Path,
    timeout_seconds: int = SEARCH_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    command_args, probe = _mcp_command_args()
    if not command_args:
        record = {
            "provider": "grok_search",
            "source_mode": "grok_search_mcp",
            "status": "not_configured",
            "records": [],
            "evidence": [],
            "warnings": [probe.get("error", "not_configured")],
            "probe": probe,
        }
        write_json_atomic(raw_response_path, record)
        write_json_atomic(evidence_path, [])
        return record

    raw_responses: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    warnings: list[str] = []
    for index, query in enumerate(queries, start=1):
        try:
            result = _call_mcp_tool(
                "web_search",
                {
                    "query": query,
                    "include_domains": include_domains,
                    "include_content": False,
                    "response_format": GROK_SEARCH_RESPONSE_FORMAT,
                },
                timeout_seconds=timeout_seconds,
            )
        except GrokSearchMCPError as exc:
            warnings.append(str(exc))
            raw_responses.append({"query": query, "error": str(exc), "probe": exc.probe, "raw_response": exc.raw_response})
            continue
        payload = result["payload"]
        raw_responses.append({"query": query, "payload": payload, "raw_response": result["raw_response"]})
        accepted, rejected = normalize_grok_payload(payload, query=query, index=index)
        records.extend(accepted)
        evidence.extend(rejected)
    write_json_atomic(raw_response_path, {"provider": "grok_search", "queries": queries, "responses": raw_responses})
    write_json_atomic(evidence_path, evidence)
    return {
        "provider": "grok_search",
        "source_mode": "grok_search_mcp",
        "status": "ok" if not warnings else "warning",
        "queries": queries,
        "records": records,
        "evidence": evidence,
        "warnings": warnings,
        "raw_response_path": str(raw_response_path),
        "evidence_path": str(evidence_path),
    }
