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
DEFAULT_MODEL_FALLBACKS = [
    "grok-4.20-multi-agent-xhigh",
    "grok-4.20-multi-agent-high",
    "grok-4.20-multi-agent-medium",
    "grok-4.20-multi-agent-console",
    "grok-4.3-high",
]
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
PAGE_CHROME_PATTERNS = (
    "search results",
    "advanced search",
    "enable javascript",
    "cookie policy",
    "access denied",
    "just a moment",
    "cloudflare",
    "sign in",
    "subscribe to",
    "all results",
)
GROK_DIAGNOSTICS_SCHEMA_VERSION = "paper-source-grok-search-diagnostics-v1"
RETRYABLE_FAILURE_STAGES = {
    "provider_runtime_failure",
    "timeout_or_budget_cutoff",
    "source_fallback_or_low_confidence_provider_output",
    "parser_or_normalization_failure",
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


def _call_mcp_tool(
    tool_name: str,
    arguments: dict[str, Any],
    timeout_seconds: int,
    *,
    env_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    command_args, probe = _mcp_command_args()
    if not command_args:
        raise GrokSearchMCPError("grok-search MCP server is not configured", probe=probe)
    process_env = os.environ.copy()
    if env_overrides:
        process_env.update(env_overrides)
    process = subprocess.Popen(
        command_args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=process_env,
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


def _host_from_url(url: str) -> str:
    if "://" not in url:
        return ""
    return url.split("://", 1)[1].split("/", 1)[0].lower()


def _host_is_paperish(host: str) -> bool:
    return host in PAPER_HOST_HINTS or any(host.endswith(f".{hint}") for hint in PAPER_HOST_HINTS)


def _looks_like_page_chrome(source: dict[str, Any]) -> bool:
    text = " ".join(
        str(source.get(key) or "")
        for key in ("title", "name", "content", "snippet", "summary")
    ).lower()
    return any(pattern in text for pattern in PAGE_CHROME_PATTERNS)


def _explicit_doi(source: dict[str, Any], url: str) -> str | None:
    doi_field = str(source.get("doi") or "").strip()
    if doi_field:
        return _first_match(DOI_PATTERN, doi_field)
    host = _host_from_url(url)
    if host in {"doi.org", "dx.doi.org"}:
        return _first_match(DOI_PATTERN, url)
    return None


def _explicit_arxiv_id(source: dict[str, Any], url: str) -> str | None:
    arxiv_field = str(source.get("arxiv_id") or "").strip()
    if arxiv_field:
        return _first_match(ARXIV_ID_PATTERN, arxiv_field)
    host = _host_from_url(url)
    if host == "arxiv.org" or host.endswith(".arxiv.org"):
        return _first_match(ARXIV_ID_PATTERN, url)
    return None


def _classify_grok_source(source: dict[str, Any]) -> tuple[str, str | None]:
    title = str(source.get("title") or "").strip()
    url = _source_url(source)
    content = str(source.get("content") or source.get("snippet") or source.get("summary") or "")
    explicit_doi = _explicit_doi(source, url)
    explicit_arxiv_id = _explicit_arxiv_id(source, url)
    host = _host_from_url(url)
    if _looks_like_page_chrome(source):
        return "quarantined", "page_chrome_or_non_paper_extraction"
    if explicit_doi:
        return "candidate_usable", None
    if explicit_arxiv_id and title:
        return "candidate_usable", None
    if explicit_arxiv_id:
        return "evidence_only", "weak_identity_extraction"
    regex_only_doi = _first_match(DOI_PATTERN, content, title)
    regex_only_arxiv = _first_match(ARXIV_ID_PATTERN, content, title)
    if regex_only_doi or regex_only_arxiv:
        return "evidence_only", "regex_identifier_without_support"
    if _host_is_paperish(host) and title:
        return "candidate_usable", None
    if source.get("authors") and (source.get("year") or source.get("published_date")) and title:
        return "candidate_usable", None
    if url:
        return "evidence_only", "missing_stable_paper_identity"
    return "quarantined", "missing_stable_paper_identity"


def _looks_like_paper(source: dict[str, Any]) -> tuple[bool, str | None]:
    state, reason = _classify_grok_source(source)
    return state == "candidate_usable", reason


def _normalize_source(source: dict[str, Any], *, query: str, index: int) -> dict[str, Any]:
    title = str(source.get("title") or source.get("name") or "").strip()
    url = _source_url(source)
    content = str(source.get("content") or source.get("snippet") or source.get("summary") or "")
    doi = source.get("doi") or _explicit_doi(source, url)
    arxiv_id = source.get("arxiv_id") or _explicit_arxiv_id(source, url)
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
        quality_state, reason = _classify_grok_source(source)
        if quality_state == "candidate_usable":
            normalized = _normalize_source(source, query=query, index=index)
            normalized["grok_quality_state"] = quality_state
            accepted.append(normalized)
        else:
            evidence.append(
                {
                    "provider": "grok_search",
                    "query": query,
                    "title": source.get("title") or source.get("name"),
                    "url": _source_url(source),
                    "reason": reason or "rejected",
                    "quality_state": quality_state,
                    "raw_record": source,
                }
            )
    return accepted, evidence


def _new_grok_diagnostics() -> dict[str, Any]:
    return {
        "schema_version": GROK_DIAGNOSTICS_SCHEMA_VERSION,
        "returned_count": 0,
        "usable_count": 0,
        "evidence_only_count": 0,
        "quarantined_count": 0,
        "query_count": 0,
        "retry_attempts": [],
        "retryable": False,
        "failure_stage": None,
        "retry_outcome": "not_needed",
        "elapsed_ms": 0,
    }


def _summarize_quality(records: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> dict[str, int]:
    evidence_only_count = 0
    quarantined_count = 0
    for item in evidence:
        state = str(item.get("quality_state") or "")
        if state == "evidence_only":
            evidence_only_count += 1
        elif state == "quarantined":
            quarantined_count += 1
    return {
        "usable_count": len(records),
        "evidence_only_count": evidence_only_count,
        "quarantined_count": quarantined_count,
    }


def _failure_stage_from_payload(payload: dict[str, Any], *, accepted_count: int, evidence: list[dict[str, Any]]) -> str | None:
    if _grok_provider_retryable(payload):
        return "source_fallback_or_low_confidence_provider_output"
    sources = payload.get("sources")
    if not isinstance(sources, list):
        return "parser_or_normalization_failure"
    if accepted_count:
        return None
    reasons = [str(item.get("reason") or "") for item in evidence]
    if any(reason == "page_chrome_or_non_paper_extraction" for reason in reasons):
        return "page_chrome_or_non_paper_extraction"
    if any(reason in {"missing_stable_paper_identity", "regex_identifier_without_support"} for reason in reasons):
        return "weak_identity_extraction"
    if sources:
        return "parser_or_normalization_failure"
    return None


def _retryable_failure_stage(stage: str | None) -> bool:
    return bool(stage in RETRYABLE_FAILURE_STAGES)


def _retry_query(query: str) -> str:
    return f"{query} scholarly article DOI arXiv publisher metadata"


def _configured_model_fallbacks() -> list[str]:
    configured = os.environ.get("PAPER_SOURCE_GROK_MODEL_FALLBACKS", "")
    configured_models = [item.strip() for item in re.split(r"[,;\s]+", configured) if item.strip()]
    primary = os.environ.get("OPENAI_COMPATIBLE_MODEL", "").strip()
    models = [primary, *configured_models, *DEFAULT_MODEL_FALLBACKS]
    return list(dict.fromkeys(model for model in models if model))


def _grok_provider_retryable(payload: dict[str, Any]) -> bool:
    fallback_reason = str(payload.get("fallback_reason") or "")
    search_provider = str(payload.get("search_provider") or "")
    return (bool(payload.get("fallback_used")) and fallback_reason == "grok_provider_error") or search_provider == "source_fallback"


def _call_web_search_with_model_fallbacks(
    *,
    arguments: dict[str, Any],
    timeout_seconds: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    last_result: dict[str, Any] | None = None
    for model in _configured_model_fallbacks():
        try:
            result = _call_mcp_tool(
                "web_search",
                arguments,
                timeout_seconds=timeout_seconds,
                env_overrides={"OPENAI_COMPATIBLE_MODEL": model},
            )
        except GrokSearchMCPError as exc:
            attempts.append({"model": model, "status": "error", "error": str(exc), "probe": exc.probe})
            continue
        payload = result["payload"]
        attempts.append(
            {
                "model": model,
                "status": "retryable_fallback" if _grok_provider_retryable(payload) else "ok",
                "search_provider": payload.get("search_provider"),
                "fallback_used": payload.get("fallback_used"),
                "fallback_reason": payload.get("fallback_reason"),
                "sources_count": payload.get("sources_count"),
            }
        )
        last_result = result
        if not _grok_provider_retryable(payload):
            result["model_attempts"] = attempts
            return result, attempts
    if last_result is not None:
        last_result["model_attempts"] = attempts
        return last_result, attempts
    raise GrokSearchMCPError(
        "grok-search MCP web_search failed for all configured model fallbacks",
        raw_response={"model_attempts": attempts},
    )


def discover_grok(
    *,
    queries: list[str],
    include_domains: list[str],
    raw_response_path: Path,
    evidence_path: Path,
    timeout_seconds: int = SEARCH_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    started = time.monotonic()
    diagnostics = _new_grok_diagnostics()
    diagnostics["query_count"] = len(queries)
    command_args, probe = _mcp_command_args()
    if not command_args:
        diagnostics.update(
            {
                "failure_stage": "not_configured_or_disabled",
                "retryable": False,
                "retry_outcome": "not_retryable",
                "elapsed_ms": int((time.monotonic() - started) * 1000),
            }
        )
        record = {
            "provider": "grok_search",
            "source_mode": "grok_search_mcp",
            "status": "not_configured",
            "records": [],
            "evidence": [],
            "warnings": [probe.get("error", "not_configured")],
            "probe": probe,
            "diagnostics": diagnostics,
        }
        write_json_atomic(raw_response_path, record)
        write_json_atomic(evidence_path, [])
        return record

    raw_responses: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    warnings: list[str] = []
    for index, query in enumerate(queries, start=1):
        query_started = time.monotonic()
        try:
            result, model_attempts = _call_web_search_with_model_fallbacks(
                arguments={
                    "query": query,
                    "include_domains": include_domains,
                    "include_content": False,
                    "response_format": GROK_SEARCH_RESPONSE_FORMAT,
                },
                timeout_seconds=timeout_seconds,
            )
        except GrokSearchMCPError as exc:
            warnings.append(str(exc))
            diagnostics["failure_stage"] = diagnostics.get("failure_stage") or "provider_runtime_failure"
            diagnostics["retryable"] = True
            raw_responses.append({"query": query, "error": str(exc), "probe": exc.probe, "raw_response": exc.raw_response})
            continue
        payload = result["payload"]
        accepted, rejected = normalize_grok_payload(payload, query=query, index=index)
        diagnostics["returned_count"] += len(payload.get("sources") or []) if isinstance(payload.get("sources"), list) else 0
        stage = _failure_stage_from_payload(payload, accepted_count=len(accepted), evidence=rejected)
        if stage == "source_fallback_or_low_confidence_provider_output" and accepted:
            for record in accepted:
                rejected.append(
                    {
                        "provider": "grok_search",
                        "query": query,
                        "title": record.get("title"),
                        "url": record.get("url"),
                        "reason": stage,
                        "quality_state": "evidence_only",
                        "raw_record": record.get("raw_record", {}),
                    }
                )
            accepted = []
        retry_attempt: dict[str, Any] | None = None
        if stage and _retryable_failure_stage(stage):
            retry_query = _retry_query(query)
            retry_started = time.monotonic()
            retry_attempt = {
                "attempt": 2,
                "reason": stage,
                "query": retry_query,
                "include_domains": include_domains,
                "status": "not_run",
            }
            try:
                retry_result, retry_model_attempts = _call_web_search_with_model_fallbacks(
                    arguments={
                        "query": retry_query,
                        "include_domains": include_domains,
                        "include_content": False,
                        "response_format": GROK_SEARCH_RESPONSE_FORMAT,
                    },
                    timeout_seconds=timeout_seconds,
                )
            except GrokSearchMCPError as exc:
                retry_attempt.update(
                    {
                        "status": "error",
                        "error": str(exc),
                        "elapsed_ms": int((time.monotonic() - retry_started) * 1000),
                    }
                )
                warnings.append(str(exc))
            else:
                retry_payload = retry_result["payload"]
                retry_accepted, retry_rejected = normalize_grok_payload(retry_payload, query=query, index=index)
                retry_stage = _failure_stage_from_payload(
                    retry_payload,
                    accepted_count=len(retry_accepted),
                    evidence=retry_rejected,
                )
                retry_attempt.update(
                    {
                        "status": "recovered" if retry_accepted else "no_recovery",
                        "failure_stage_after_retry": retry_stage,
                        "returned_count": len(retry_payload.get("sources") or [])
                        if isinstance(retry_payload.get("sources"), list)
                        else 0,
                        "usable_count": len(retry_accepted),
                        "evidence_only_count": _summarize_quality(retry_accepted, retry_rejected)["evidence_only_count"],
                        "quarantined_count": _summarize_quality(retry_accepted, retry_rejected)["quarantined_count"],
                        "elapsed_ms": int((time.monotonic() - retry_started) * 1000),
                        "model_attempts": retry_model_attempts,
                    }
                )
                raw_responses.append(
                    {
                        "query": retry_query,
                        "retry_of": query,
                        "payload": retry_payload,
                        "raw_response": retry_result["raw_response"],
                        "model_attempts": retry_model_attempts,
                    }
                )
                diagnostics["returned_count"] += (
                    len(retry_payload.get("sources") or []) if isinstance(retry_payload.get("sources"), list) else 0
                )
                accepted.extend(retry_accepted)
                rejected.extend(retry_rejected)
                stage = retry_stage
            diagnostics["retry_attempts"].append(retry_attempt)
        if stage and not accepted and not diagnostics.get("failure_stage"):
            diagnostics["failure_stage"] = stage
            diagnostics["retryable"] = _retryable_failure_stage(stage)
        raw_responses.append(
            {
                "query": query,
                "payload": payload,
                "raw_response": result["raw_response"],
                "model_attempts": model_attempts,
                "failure_stage": stage,
                "elapsed_ms": int((time.monotonic() - query_started) * 1000),
            }
        )
        records.extend(accepted)
        evidence.extend(rejected)
    quality_summary = _summarize_quality(records, evidence)
    diagnostics.update(quality_summary)
    if records and diagnostics.get("retry_attempts"):
        diagnostics["failure_stage"] = None
        diagnostics["retryable"] = False
    else:
        diagnostics["retryable"] = _retryable_failure_stage(str(diagnostics.get("failure_stage") or ""))
    if diagnostics["retry_attempts"]:
        if records:
            diagnostics["retry_outcome"] = "recovered"
        elif any(item.get("status") == "error" for item in diagnostics["retry_attempts"] if isinstance(item, dict)):
            diagnostics["retry_outcome"] = "failed"
        else:
            diagnostics["retry_outcome"] = "no_recovery"
    elif diagnostics.get("failure_stage") and not diagnostics.get("retryable"):
        diagnostics["retry_outcome"] = "not_retryable"
    if not diagnostics.get("failure_stage"):
        if warnings:
            diagnostics["failure_stage"] = "provider_runtime_failure"
            diagnostics["retryable"] = True
        elif not records and evidence:
            reasons = [str(item.get("reason") or "") for item in evidence]
            diagnostics["failure_stage"] = (
                "page_chrome_or_non_paper_extraction"
                if "page_chrome_or_non_paper_extraction" in reasons
                else "weak_identity_extraction"
            )
        elif not records:
            diagnostics["failure_stage"] = "parser_or_normalization_failure"
            diagnostics["retryable"] = True
    diagnostics["elapsed_ms"] = int((time.monotonic() - started) * 1000)
    write_json_atomic(
        raw_response_path,
        {
            "provider": "grok_search",
            "queries": queries,
            "responses": raw_responses,
            "diagnostics": diagnostics,
        },
    )
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
        "diagnostics": diagnostics,
    }
