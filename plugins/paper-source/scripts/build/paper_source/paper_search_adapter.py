from __future__ import annotations

import ast
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

from paper_source.artifacts import read_json
from paper_source.runtime_config import apply_runtime_config


DEFAULT_SOURCES = ["arxiv", "semantic", "openalex", "crossref", "dblp"]
COMMAND_UNAVAILABLE = (
    "paper-search command unavailable; install paper-search-mcp or configure "
    "PAPER_SOURCE_PAPER_SEARCH_COMMAND"
)
PROBE_TIMEOUT_SECONDS = 60
SEARCH_TIMEOUT_SECONDS = 180
MCP_PROTOCOL_VERSION = "2025-11-25"
DEFAULT_MCP_COMMAND_ARGS = ["python", "-m", "paper_search_mcp.server"]
YEAR_PREFIX_RE = re.compile(r"^(19|20)\d{2}")
OA_FALLBACK_CHAIN = ["source-native", "openaire", "core", "europepmc", "pmc", "unpaywall"]
SOURCE_CAPABILITIES = {
    "arxiv": {"search": "supported", "download": "supported", "read": "supported"},
    "pubmed": {"search": "supported", "download": "unsupported", "read": "info-only"},
    "biorxiv": {"search": "supported", "download": "supported", "read": "supported"},
    "medrxiv": {"search": "supported", "download": "supported", "read": "supported"},
    "google_scholar": {"search": "unstable", "download": "unsupported", "read": "unsupported"},
    "iacr": {"search": "supported", "download": "supported", "read": "supported"},
    "semantic": {"search": "supported", "download": "oa", "read": "oa"},
    "crossref": {"search": "supported", "download": "unsupported", "read": "info-only"},
    "openalex": {"search": "supported", "download": "unsupported", "read": "info-only"},
    "pmc": {"search": "supported", "download": "oa", "read": "oa"},
    "core": {"search": "supported", "download": "record-dependent", "read": "record-dependent"},
    "europepmc": {"search": "supported", "download": "oa", "read": "oa"},
    "dblp": {"search": "supported", "download": "unsupported", "read": "info-only"},
    "openaire": {"search": "supported", "download": "unsupported", "read": "unsupported"},
    "citeseerx": {"search": "unstable", "download": "record-dependent", "read": "record-dependent"},
    "doaj": {"search": "supported", "download": "url-dependent", "read": "url-dependent"},
    "base": {"search": "unstable", "download": "record-dependent", "read": "record-dependent"},
    "zenodo": {"search": "supported", "download": "record-dependent", "read": "record-dependent"},
    "hal": {"search": "supported", "download": "record-dependent", "read": "record-dependent"},
    "ssrn": {"search": "unstable", "download": "best-effort", "read": "best-effort"},
    "unpaywall": {"search": "doi-lookup", "download": "unsupported", "read": "unsupported"},
    "scihub": {"search": "fallback-only", "download": "optional", "read": "unsupported"},
}

PROVIDER_ENV_REQUIREMENTS = {
    "unpaywall": {
        "env": "PAPER_SEARCH_MCP_UNPAYWALL_EMAIL",
        "importance": "required",
        "gap": "unpaywall_email_missing",
        "reason": "Unpaywall DOI lookup is skipped without an email.",
    },
    "core": {
        "env": "PAPER_SEARCH_MCP_CORE_API_KEY",
        "importance": "recommended",
        "gap": "core_api_key_missing",
        "reason": "CORE works better with a free API key and may rate-limit keyless access.",
    },
    "semantic": {
        "env": "PAPER_SEARCH_MCP_SEMANTIC_SCHOLAR_API_KEY",
        "importance": "optional",
        "gap": "semantic_scholar_api_key_missing",
        "reason": "Semantic Scholar works keyless but a key improves rate limits.",
    },
    "google_scholar": {
        "env": "PAPER_SEARCH_MCP_GOOGLE_SCHOLAR_PROXY_URL",
        "importance": "optional",
        "gap": "google_scholar_proxy_missing",
        "reason": "Google Scholar is often blocked by bot detection without a proxy.",
    },
    "doaj": {
        "env": "PAPER_SEARCH_MCP_DOAJ_API_KEY",
        "importance": "optional",
        "gap": "doaj_api_key_missing",
        "reason": "DOAJ key raises rate limits.",
    },
    "zenodo": {
        "env": "PAPER_SEARCH_MCP_ZENODO_ACCESS_TOKEN",
        "importance": "optional",
        "gap": "zenodo_access_token_missing",
        "reason": "Zenodo token is only needed for private records or higher limits.",
    },
}


def paper_search_source_capabilities(sources: list[str] | None = None) -> dict[str, dict]:
    selected = sources or sorted(SOURCE_CAPABILITIES)
    return {
        source: dict(SOURCE_CAPABILITIES[source])
        for source in selected
        if source in SOURCE_CAPABILITIES
    }


def paper_search_provider_readiness(sources: list[str] | None = None) -> dict[str, dict]:
    selected = set(sources or PROVIDER_ENV_REQUIREMENTS)
    selected.update({"unpaywall"} if not sources else set())
    readiness = {}
    for provider, requirement in PROVIDER_ENV_REQUIREMENTS.items():
        if provider not in selected:
            continue
        env_name = requirement["env"]
        present = bool(os.environ.get(env_name))
        importance = requirement["importance"]
        status = "set" if present else f"missing_{importance}_env"
        readiness[provider] = {
            "status": status,
            "env": env_name,
            "importance": importance,
            "configured": present,
            "provider_gap": requirement.get("gap") if not present else None,
            "reason": requirement["reason"],
        }
    return readiness


DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[^\s\"'<>]+\b", re.IGNORECASE)
ARXIV_ID_PATTERN = re.compile(
    r"(?i)(?:arxiv:\s*|arxiv\.org/(?:abs|pdf)/)?(\d{4}\.\d{4,5}(?:v\d+)?)"
)
EXACT_SOURCE_POLICIES = {
    "doi": {
        "source_policy": "doi_exact",
        "sources": ["unpaywall", "crossref", "openalex", "semantic"],
        "demotion_reason": "exact_doi_lookup",
    },
    "arxiv_id": {
        "source_policy": "arxiv_exact",
        "sources": ["arxiv"],
        "demotion_reason": "exact_arxiv_lookup",
    },
    "title": {
        "source_policy": "title_exact",
        "sources": ["semantic", "openalex", "crossref"],
        "demotion_reason": "exact_title_lookup",
    },
}


def _clean_doi(value: str) -> str:
    text = re.sub(r"^https?://(dx\.)?doi\.org/", "", value.strip(), flags=re.IGNORECASE)
    text = re.sub(r"^doi:\s*", "", text, flags=re.IGNORECASE)
    return text.strip().strip(".,;")


def _detect_exact_lookup(query: str | None) -> dict | None:
    text = str(query or "").strip()
    if not text:
        return None
    title_match = re.fullmatch(r"""(?is)\s*title:\s*["'](.+?)["']\s*""", text)
    if title_match:
        value = " ".join(title_match.group(1).split())
        if value:
            policy = EXACT_SOURCE_POLICIES["title"]
            return {"kind": "title", "value": value, "source_policy": policy["source_policy"]}
    doi_match = DOI_PATTERN.search(text)
    if doi_match:
        policy = EXACT_SOURCE_POLICIES["doi"]
        return {
            "kind": "doi",
            "value": _clean_doi(doi_match.group(0)),
            "source_policy": policy["source_policy"],
        }
    arxiv_match = ARXIV_ID_PATTERN.search(text)
    if arxiv_match and (
        "arxiv" in text.lower()
        or re.fullmatch(r"\s*\d{4}\.\d{4,5}(?:v\d+)?\s*", text, flags=re.IGNORECASE)
    ):
        policy = EXACT_SOURCE_POLICIES["arxiv_id"]
        return {
            "kind": "arxiv_id",
            "value": arxiv_match.group(1),
            "source_policy": policy["source_policy"],
        }
    return None


def _dedupe_sources(sources: list[str] | None) -> list[str]:
    requested_sources: list[str] = []
    seen: set[str] = set()
    for source in sources or DEFAULT_SOURCES:
        source_name = str(source).strip().lower()
        if not source_name or source_name in seen:
            continue
        seen.add(source_name)
        requested_sources.append(source_name)
    return requested_sources


def plan_source_routing(
    sources: list[str] | None = None,
    *,
    include_unstable: bool = False,
    query: str | None = None,
) -> dict:
    explicit_sources = sources is not None
    requested_sources = _dedupe_sources(sources)
    exact_lookup = _detect_exact_lookup(query)
    if exact_lookup:
        policy = EXACT_SOURCE_POLICIES[exact_lookup["kind"]]
        policy_sources = [source for source in policy["sources"] if source in SOURCE_CAPABILITIES]
        requested_set = set(requested_sources)
        if explicit_sources:
            selected_sources = [source for source in policy_sources if source in requested_set] or policy_sources
        else:
            selected_sources = policy_sources
        demoted_sources = [
            {"source": source, "reason": policy["demotion_reason"]}
            for source in requested_sources
            if source not in selected_sources
        ]
        provider_readiness = paper_search_provider_readiness(selected_sources)
        provider_risks = [
            {
                "provider": provider,
                "status": state.get("status"),
                "env": state.get("env"),
                "importance": state.get("importance"),
                "reason": state.get("reason"),
            }
            for provider, state in sorted(provider_readiness.items())
            if isinstance(state, dict)
            and state.get("status") not in {"set"}
            and state.get("importance") in {"required", "recommended"}
        ]
        provider_gaps = [
            {
                "provider": risk["provider"],
                "provider_gap": provider_readiness.get(risk["provider"], {}).get("provider_gap")
                or f"{risk.get('provider')}_missing_env",
                "status": risk.get("status"),
                "env": risk.get("env"),
                "importance": risk.get("importance"),
                "reason": risk.get("reason"),
            }
            for risk in provider_risks
        ]
        return {
            "requested_sources": requested_sources,
            "selected_sources": selected_sources,
            "demoted_sources": demoted_sources,
            "provider_readiness": provider_readiness,
            "provider_risks": provider_risks,
            "provider_gaps": provider_gaps,
            "include_unstable": include_unstable,
            "exact_lookup": exact_lookup,
        }

    selected_sources: list[str] = []
    demoted_sources: list[dict] = []
    seen: set[str] = set()
    for source in requested_sources:
        source_name = source.strip().lower()
        if not source_name or source_name in seen:
            continue
        seen.add(source_name)
        capability = SOURCE_CAPABILITIES.get(source_name, {})
        if capability.get("search") == "unstable" and not include_unstable:
            demoted_sources.append({"source": source_name, "reason": "unstable_source"})
            continue
        if capability.get("search") == "doi-lookup":
            demoted_sources.append({"source": source_name, "reason": "doi_lookup_source"})
            continue
        selected_sources.append(source_name)

    if not selected_sources:
        selected_sources = [
            source
            for source in requested_sources
            if source.lower() not in {item["source"] for item in demoted_sources}
        ] or list(DEFAULT_SOURCES)

    provider_readiness = paper_search_provider_readiness(selected_sources)
    provider_risks = [
        {
            "provider": provider,
            "status": state.get("status"),
            "env": state.get("env"),
            "importance": state.get("importance"),
            "reason": state.get("reason"),
        }
        for provider, state in sorted(provider_readiness.items())
        if isinstance(state, dict)
        and state.get("status") not in {"set"}
        and state.get("importance") in {"required", "recommended"}
    ]
    provider_gaps = [
        {
            "provider": risk["provider"],
            "provider_gap": provider_readiness.get(risk["provider"], {}).get("provider_gap")
            or f"{risk.get('provider')}_missing_env",
            "status": risk.get("status"),
            "env": risk.get("env"),
            "importance": risk.get("importance"),
            "reason": risk.get("reason"),
        }
        for risk in provider_risks
    ]
    return {
        "requested_sources": requested_sources,
        "selected_sources": selected_sources,
        "demoted_sources": demoted_sources,
        "provider_readiness": provider_readiness,
        "provider_risks": provider_risks,
        "provider_gaps": provider_gaps,
        "include_unstable": include_unstable,
    }


class MCPToolError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        probe: dict | None = None,
        raw_response: dict | None = None,
        stderr: str = "",
    ) -> None:
        super().__init__(message)
        self.probe = probe or {}
        self.raw_response = raw_response or {}
        self.stderr = stderr


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


def _split_command_line(command_line: str) -> list[str]:
    return [token.strip("\"'") for token in shlex.split(command_line, posix=False)]


def _paper_search_mcp_disabled() -> bool:
    return os.environ.get("PAPER_SOURCE_PAPER_SEARCH_MCP_DISABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def _mcp_empty_fallback_enabled() -> bool:
    return os.environ.get("PAPER_SOURCE_PAPER_SEARCH_MCP_EMPTY_FALLBACK", "1").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _mcp_command_tokens(command: str | None = None) -> list[str]:
    selected_command = command or os.environ.get("PAPER_SOURCE_PAPER_SEARCH_MCP_COMMAND")
    tokens = _split_command_line(selected_command) if selected_command else list(DEFAULT_MCP_COMMAND_ARGS)
    extra_args = os.environ.get("PAPER_SOURCE_PAPER_SEARCH_MCP_ARGS")
    if extra_args:
        tokens.extend(_split_command_line(extra_args))
    return tokens


def _mcp_command_args(command: str | None = None) -> tuple[list[str] | None, dict]:
    tokens = _mcp_command_tokens(command)
    if not tokens:
        return None, {
            "available": False,
            "command": "",
            "args": [],
            "transport": "stdio",
            "error": "command_not_configured",
        }
    resolved = _resolve_command(tokens[0])
    if not resolved:
        return None, {
            "available": False,
            "command": tokens[0],
            "args": tokens[1:],
            "transport": "stdio",
            "error": "command_not_found",
        }
    command_args = _command_args(resolved, tokens[1:])
    return command_args, {
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


def _write_jsonrpc(process: subprocess.Popen[str], payload: dict) -> None:
    if process.stdin is None:
        raise MCPToolError("paper-search MCP stdin is unavailable")
    process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
    process.stdin.flush()


def _close_process_stdin(process: subprocess.Popen[str]) -> None:
    if process.stdin is None:
        return
    try:
        process.stdin.close()
    except OSError:
        pass


def _read_jsonrpc_response(
    *,
    process: subprocess.Popen[str],
    stdout_lines: queue.Queue[str],
    stderr_lines: queue.Queue[str],
    expected_id: int,
    deadline: float,
    probe: dict,
) -> dict:
    ignored_stdout: list[str] = []
    while time.monotonic() < deadline:
        remaining = max(0.05, min(0.25, deadline - time.monotonic()))
        try:
            line = stdout_lines.get(timeout=remaining)
        except queue.Empty:
            if process.poll() is not None:
                stderr = "".join(_drain_queue(stderr_lines)).strip()
                stdout = "".join(ignored_stdout + _drain_queue(stdout_lines)).strip()
                raise MCPToolError(
                    "paper-search MCP server exited before response",
                    probe={**probe, "available": False, "error": "server_exited"},
                    raw_response={"stdout": stdout, "stderr": stderr, "returncode": process.returncode},
                    stderr=stderr,
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
                raise MCPToolError(
                    message_text or "paper-search MCP tool call failed",
                    probe={**probe, "available": False, "error": "jsonrpc_error"},
                    raw_response=message,
                    stderr="".join(_drain_queue(stderr_lines)).strip(),
                )
            return message
    stderr = "".join(_drain_queue(stderr_lines)).strip()
    raise MCPToolError(
        "paper-search MCP tool call timed out",
        probe={**probe, "available": False, "error": "timeout"},
        raw_response={"stderr": stderr, "timeout_seconds": max(0, deadline - time.monotonic())},
        stderr=stderr,
    )


def _extract_mcp_text_content(result: dict) -> str:
    content = result.get("content") if isinstance(result, dict) else None
    if not isinstance(content, list):
        return ""
    text_parts = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            text_parts.append(str(item.get("text") or ""))
    return "\n".join(part for part in text_parts if part)


def _extract_mcp_tool_payload(result: dict) -> dict:
    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        return structured
    text = _extract_mcp_text_content(result)
    if text:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {"text": text}
        if isinstance(parsed, dict):
            return parsed
        return {"value": parsed}
    return {}


def _unwrap_mcp_payload(payload: dict) -> dict:
    if isinstance(payload.get("result"), dict):
        return payload["result"]
    return payload


def _call_mcp_tool(tool_name: str, arguments: dict, timeout_seconds: int) -> dict:
    if _paper_search_mcp_disabled():
        raise MCPToolError(
            "paper-search MCP server disabled",
            probe={"available": False, "transport": "stdio", "error": "disabled"},
        )
    command_args, probe = _mcp_command_args()
    if command_args is None:
        raise MCPToolError("paper-search MCP command unavailable", probe=probe)
    process = subprocess.Popen(
        command_args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    stdout_lines: queue.Queue[str] = queue.Queue()
    stderr_lines: queue.Queue[str] = queue.Queue()
    stdout_thread = threading.Thread(
        target=_enqueue_stream_lines,
        args=(process.stdout, stdout_lines),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_enqueue_stream_lines,
        args=(process.stderr, stderr_lines),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()
    try:
        deadline = time.monotonic() + timeout_seconds
        _write_jsonrpc(
            process,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "paper-source", "version": "0.2.5"},
                },
            },
        )
        initialize_response = _read_jsonrpc_response(
            process=process,
            stdout_lines=stdout_lines,
            stderr_lines=stderr_lines,
            expected_id=1,
            deadline=deadline,
            probe=probe,
        )
        initialize_result = initialize_response.get("result") or {}
        probe = {
            **probe,
            "available": True,
            "protocol_version": initialize_result.get("protocolVersion"),
            "server_info": initialize_result.get("serverInfo", {}),
        }
        _write_jsonrpc(
            process,
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            },
        )
        _write_jsonrpc(
            process,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            },
        )
        tool_response = _read_jsonrpc_response(
            process=process,
            stdout_lines=stdout_lines,
            stderr_lines=stderr_lines,
            expected_id=2,
            deadline=deadline,
            probe=probe,
        )
        result = tool_response.get("result") or {}
        if result.get("isError"):
            text = _extract_mcp_text_content(result)
            raise MCPToolError(
                text or "paper-search MCP tool returned an error",
                probe={**probe, "available": False, "error": "tool_error"},
                raw_response=tool_response,
                stderr="".join(_drain_queue(stderr_lines)).strip(),
            )
        payload = _extract_mcp_tool_payload(result)
        return {
            "payload": _unwrap_mcp_payload(payload),
            "probe": probe,
            "raw_response": tool_response,
        }
    except OSError as exc:
        raise MCPToolError(str(exc), probe={**probe, "available": False, "error": "spawn_failed"}) from exc
    finally:
        _close_process_stdin(process)
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def probe_paper_search_mcp_server(timeout_seconds: int = PROBE_TIMEOUT_SECONDS) -> dict:
    apply_runtime_config()
    if _paper_search_mcp_disabled():
        return {"available": False, "transport": "stdio", "error": "disabled"}
    command_args, probe = _mcp_command_args()
    if command_args is None:
        return probe
    process = subprocess.Popen(
        command_args,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    stdout_lines: queue.Queue[str] = queue.Queue()
    stderr_lines: queue.Queue[str] = queue.Queue()
    stdout_thread = threading.Thread(
        target=_enqueue_stream_lines,
        args=(process.stdout, stdout_lines),
        daemon=True,
    )
    stderr_thread = threading.Thread(
        target=_enqueue_stream_lines,
        args=(process.stderr, stderr_lines),
        daemon=True,
    )
    stdout_thread.start()
    stderr_thread.start()
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
                    "clientInfo": {"name": "paper-source-doctor", "version": "0.2.5"},
                },
            },
        )
        initialize_response = _read_jsonrpc_response(
            process=process,
            stdout_lines=stdout_lines,
            stderr_lines=stderr_lines,
            expected_id=1,
            deadline=time.monotonic() + timeout_seconds,
            probe=probe,
        )
        initialize_result = initialize_response.get("result") or {}
        return {
            **probe,
            "available": True,
            "protocol_version": initialize_result.get("protocolVersion"),
            "server_info": initialize_result.get("serverInfo", {}),
        }
    except MCPToolError as exc:
        return _mcp_failure_payload(exc)
    except OSError as exc:
        return {**probe, "available": False, "error": str(exc)}
    finally:
        _close_process_stdin(process)
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


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


def _parse_year_prefix(value: object) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 1900 <= value <= 2099 else None
    text = str(value).strip()
    match = YEAR_PREFIX_RE.match(text)
    if not match:
        return None
    try:
        return int(match.group(0))
    except (TypeError, ValueError):
        return None


def _extract_year(record: dict, extra: dict) -> int | None:
    for key in ("year", "published_year"):
        if record.get(key) is not None:
            year = _parse_year_prefix(record.get(key))
            if year is not None:
                return year
    for key in ("published_date", "updated_date", "publication_date", "date"):
        value = record.get(key) or extra.get(key)
        year = _parse_year_prefix(value)
        if year is not None:
            return year
    return None


def _extract_arxiv_id(record: dict) -> str | None:
    if record.get("arxiv_id"):
        return str(record["arxiv_id"])
    source = str(record.get("source") or "").lower()
    paper_id = record.get("paper_id")
    if source == "arxiv" and paper_id:
        return str(paper_id)
    return None


def _citation_count(record: dict) -> int | None:
    for key in ("citation_count", "citations"):
        if record.get(key) is not None:
            return int(record.get(key) or 0)
    return None


def _normalize_paper_search_record(record: dict) -> dict:
    extra = _parse_extra(record.get("extra"))
    normalized = {
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
        "raw_record": record,
    }
    citation_count = _citation_count(record)
    if citation_count is not None:
        normalized["citation_count"] = citation_count
    return normalized


def _write_raw_response(raw_response_path: Path | None, payload: dict) -> str | None:
    if raw_response_path is None:
        return None
    raw_response_path.parent.mkdir(parents=True, exist_ok=True)
    raw_response_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(raw_response_path)


def _mcp_failure_payload(exc: MCPToolError) -> dict:
    return {
        "available": False,
        **(exc.probe or {}),
        "error": str(exc),
    }


def _fallback_fields(mcp_failure: dict | None) -> dict:
    if not mcp_failure:
        return {}
    return {
        "fallback_from": "paper_search_mcp",
        "fallback_error": mcp_failure.get("error", "unavailable"),
        "mcp_server_probe": mcp_failure,
    }


def _timeout_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _elapsed_ms(start: float) -> int:
    return int(round((time.perf_counter() - start) * 1000))


def _int_or_zero(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return 0


def _source_health_payload(
    *,
    sources: list[str],
    source_results: object,
    errors: object,
    timeout_seconds: int,
) -> dict[str, dict]:
    results = source_results if isinstance(source_results, dict) else {}
    error_map = errors if isinstance(errors, dict) else {}
    ordered: list[str] = []
    seen: set[str] = set()

    def add(source: object) -> None:
        source_name = str(source or "").strip()
        if not source_name or source_name in seen:
            return
        seen.add(source_name)
        ordered.append(source_name)

    for source in sources:
        add(source)
    for source in results:
        add(source)
    for source in error_map:
        add(source)

    health: dict[str, dict] = {}
    for source in ordered:
        error = str(error_map.get(source) or "").strip() or None
        result_count = _int_or_zero(results.get(source))
        status = "failed" if error else "ok" if result_count > 0 else "empty"
        health[source] = {
            "status": status,
            "result_count": result_count,
            "error": error,
            "duration_ms": None,
            "timeout_budget_seconds": timeout_seconds,
        }
    return health


def _downloaded_pdf_paths(output_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in output_dir.rglob("*")
        if path.is_file() and path.suffix.lower() == ".pdf" and path.stat().st_size > 0
    )


def _paper_read_tool_name(source: str) -> str:
    return f"read_{source.strip().lower().replace('-', '_')}_paper"


def _extract_preview_text(payload: object, raw_response: dict | None = None) -> str:
    if isinstance(payload, str):
        return payload.strip()
    if isinstance(payload, dict):
        for key in ("text", "content", "paper_text", "value"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        result = payload.get("result")
        if result is not payload:
            text = _extract_preview_text(result, raw_response)
            if text:
                return text
    if raw_response:
        result = raw_response.get("result")
        text = _extract_mcp_text_content(result) if isinstance(result, dict) else ""
        if text.strip():
            return text.strip()
    return ""


def _meaningful_preview_text(text: str) -> str:
    preview = text.strip()
    if not preview:
        return ""
    lowered = " ".join(preview.lower().split())
    unsupported_markers = (
        "unsupported",
        "not supported",
        "not implemented",
        "coming soon",
        "info-only",
        "information only",
        "read mode is not available",
        "no full text available",
        "no text available",
        "unable to extract",
    )
    if any(marker in lowered for marker in unsupported_markers):
        return ""
    return preview


def _write_preview(output_path: Path, text: str) -> dict:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text.rstrip() + "\n", encoding="utf-8")
    return {
        "output_path": str(output_path),
        "char_count": len(text.rstrip()),
        "authoritative": False,
        "replaces_mineru": False,
    }


def discover(
    query: str,
    max_results: int,
    fixture_path: Path | None = None,
    command: str | None = None,
    sources: list[str] | None = None,
    raw_response_path: Path | None = None,
    timeout_seconds: int = SEARCH_TIMEOUT_SECONDS,
) -> dict:
    apply_runtime_config()
    if fixture_path:
        records = read_json(fixture_path)
        return {
            "query": query,
            "max_results": max_results,
            "source_mode": "fixture",
            "mcp_probe": {"available": True, "command": "fixture"},
            "records": records[:max_results],
        }
    selected_sources = sources or DEFAULT_SOURCES
    mcp_failure: dict | None = None
    mcp_search_started = time.perf_counter()
    try:
        mcp_result = _call_mcp_tool(
            "search_papers",
            {
                "query": query,
                "max_results_per_source": max_results,
                "sources": ",".join(selected_sources),
            },
            timeout_seconds=timeout_seconds,
        )
    except MCPToolError as exc:
        mcp_search_duration_ms = _elapsed_ms(mcp_search_started)
        mcp_failure = _mcp_failure_payload(exc)
        mcp_failure["search_duration_ms"] = mcp_search_duration_ms
    else:
        mcp_search_duration_ms = _elapsed_ms(mcp_search_started)
        payload = _unwrap_mcp_payload(mcp_result["payload"])
        source_results = payload.get("source_results", {})
        source_errors = payload.get("errors", {})
        sources_used = payload.get("sources_used", [])
        health_sources = sources_used if isinstance(sources_used, list) and sources_used else selected_sources
        source_health = _source_health_payload(
            sources=health_sources,
            source_results=source_results,
            errors=source_errors,
            timeout_seconds=timeout_seconds,
        )
        if not payload.get("papers") and _mcp_empty_fallback_enabled():
            mcp_failure = {
                **mcp_result["probe"],
                "available": False,
                "error": "paper-search MCP search returned no papers",
                "raw_response": mcp_result.get("raw_response", {}),
                "source_results": source_results,
                "source_health": source_health,
                "timeout_budget_seconds": timeout_seconds,
                "search_duration_ms": mcp_search_duration_ms,
                "total": payload.get("total"),
            }
        else:
            raw_path = _write_raw_response(raw_response_path, payload)
            return {
                "query": query,
                "max_results": max_results,
                "source_mode": "paper_search_mcp",
                "mcp_probe": mcp_result["probe"],
                "raw_response_path": raw_path,
                "records": [_normalize_paper_search_record(record) for record in payload.get("papers", [])][:max_results],
                "upstream": {
                    "package": "paper-search-mcp",
                    "transport": "stdio",
                    "tool": "search_papers",
                    "version_probe": mcp_result["probe"],
                    "query": payload.get("query", query),
                    "sources_requested": selected_sources,
                    "sources_used": sources_used,
                    "source_results": source_results,
                    "source_health": source_health,
                    "errors": source_errors,
                    "timeout_budget_seconds": timeout_seconds,
                    "search_duration_ms": mcp_search_duration_ms,
                    "raw_total": payload.get("raw_total"),
                    "total": payload.get("total"),
                    "raw_response": mcp_result.get("raw_response", {}),
                },
            }
    selected_command = command or os.environ.get("PAPER_SOURCE_PAPER_SEARCH_COMMAND") or "paper-search"
    probe = probe_paper_search_mcp(selected_command)
    if not probe["available"]:
        return {
            "query": query,
            "max_results": max_results,
            "source_mode": "paper_search_cli",
            "mcp_probe": probe,
            "mcp_server_probe": mcp_failure,
            "records": [],
            "error": COMMAND_UNAVAILABLE,
        }
    resolved_command = probe["command"]
    args = ["search", query, "-n", str(max_results), "-s", ",".join(selected_sources)]
    cli_search_started = time.perf_counter()
    try:
        result = _run_command(resolved_command, args, timeout_seconds=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        cli_search_duration_ms = _elapsed_ms(cli_search_started)
        stdout = _timeout_text(exc.output)
        stderr = _timeout_text(exc.stderr)
        raw_path = _write_raw_response(
            raw_response_path,
            {
                "stdout": stdout,
                "stderr": stderr,
                "returncode": None,
                "timeout_seconds": timeout_seconds,
            },
        )
        return {
            "query": query,
            "max_results": max_results,
            "source_mode": "paper_search_cli",
            "mcp_probe": probe,
            "mcp_server_probe": mcp_failure,
            "raw_response_path": raw_path,
            "records": [],
            "error": "paper-search search timed out",
            "upstream": {
                "package": "paper-search-mcp",
                "cli_command": resolved_command,
                "version_probe": probe,
                "sources_requested": selected_sources,
                "returncode": None,
                "stderr": stderr.strip(),
                "timeout_seconds": timeout_seconds,
                "timeout_budget_seconds": timeout_seconds,
                "search_duration_ms": cli_search_duration_ms,
                "source_health": _source_health_payload(
                    sources=selected_sources,
                    source_results={},
                    errors={source: "paper-search search timed out" for source in selected_sources},
                    timeout_seconds=timeout_seconds,
                ),
                **_fallback_fields(mcp_failure),
            },
        }
    cli_search_duration_ms = _elapsed_ms(cli_search_started)
    if result.returncode != 0 or not result.stdout.strip():
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
            "mcp_server_probe": mcp_failure,
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
                "timeout_budget_seconds": timeout_seconds,
                "search_duration_ms": cli_search_duration_ms,
                "source_health": _source_health_payload(
                    sources=selected_sources,
                    source_results={},
                    errors={source: "paper-search search failed" for source in selected_sources},
                    timeout_seconds=timeout_seconds,
                ),
                **_fallback_fields(mcp_failure),
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
            "mcp_server_probe": mcp_failure,
            "raw_response_path": raw_path,
            "records": [],
            "error": f"paper-search search returned invalid JSON: {exc}",
            "upstream": {
                "package": "paper-search-mcp",
                "cli_command": resolved_command,
                "version_probe": probe,
                "sources_requested": selected_sources,
                "returncode": result.returncode,
                "stderr": result.stderr.strip(),
                "timeout_budget_seconds": timeout_seconds,
                "search_duration_ms": cli_search_duration_ms,
                "source_health": _source_health_payload(
                    sources=selected_sources,
                    source_results={},
                    errors={source: "paper-search search returned invalid JSON" for source in selected_sources},
                    timeout_seconds=timeout_seconds,
                ),
                **_fallback_fields(mcp_failure),
            },
        }
    raw_path = _write_raw_response(raw_response_path, payload)
    source_results = payload.get("source_results", {})
    source_errors = payload.get("errors", {})
    sources_used = payload.get("sources_used", [])
    health_sources = sources_used if isinstance(sources_used, list) and sources_used else selected_sources
    source_health = _source_health_payload(
        sources=health_sources,
        source_results=source_results,
        errors=source_errors,
        timeout_seconds=timeout_seconds,
    )
    return {
        "query": query,
        "max_results": max_results,
        "source_mode": "paper_search_cli",
        "mcp_probe": probe,
        "mcp_server_probe": mcp_failure,
        "raw_response_path": raw_path,
        "records": [_normalize_paper_search_record(record) for record in payload.get("papers", [])][:max_results],
        "upstream": {
            "package": "paper-search-mcp",
            "cli_command": resolved_command,
            "version_probe": probe,
            "query": payload.get("query", query),
            "sources_requested": selected_sources,
            "sources_used": sources_used,
            "source_results": source_results,
            "source_health": source_health,
            "errors": source_errors,
            "timeout_budget_seconds": timeout_seconds,
            "search_duration_ms": cli_search_duration_ms,
            "raw_total": payload.get("raw_total"),
            "total": payload.get("total"),
            **_fallback_fields(mcp_failure),
        },
    }


def download_paper_pdf(
    *,
    source: str,
    paper_id: str,
    output_dir: Path,
    doi: str = "",
    title: str = "",
    use_scihub: bool = False,
    scihub_base_url: str = "https://sci-hub.se",
    stop_after_oa_fallback: bool = False,
    command: str | None = None,
    timeout_seconds: int = 120,
) -> dict:
    apply_runtime_config()
    output_dir.mkdir(parents=True, exist_ok=True)
    source_name = source.strip().lower()
    fallback_arguments = {
        "source": source_name,
        "paper_id": paper_id,
        "doi": doi or "",
        "title": title or "",
        "save_path": str(output_dir),
        "use_scihub": bool(use_scihub),
        "scihub_base_url": scihub_base_url,
    }
    mcp_failure: dict | None = None
    try:
        mcp_result = _call_mcp_tool(
            "download_with_fallback",
            fallback_arguments,
            timeout_seconds=timeout_seconds,
        )
    except MCPToolError as exc:
        mcp_failure = _mcp_failure_payload(exc)
        if stop_after_oa_fallback:
            return {
                "status": "failed",
                "mode": "paper_search_mcp_fallback_download",
                "source": source_name,
                "paper_id": paper_id,
                "doi": doi or "",
                "title": title or "",
                "use_scihub": bool(use_scihub),
                "mcp_probe": mcp_failure,
                "mcp_server_probe": mcp_failure,
                "upstream": {
                    "package": "paper-search-mcp",
                    "transport": "stdio",
                    "tool": "download_with_fallback",
                    "fallback_chain": list(OA_FALLBACK_CHAIN)
                    + (["scihub"] if use_scihub else []),
                    "use_scihub": bool(use_scihub),
                    "returncode": None,
                    "error": str(exc),
                    "raw_response": exc.raw_response or {},
                },
                "error": "paper-search OA fallback failed",
            }
    else:
        pdf_paths = _downloaded_pdf_paths(output_dir)
        if pdf_paths:
            return {
                "status": "success",
                "mode": "paper_search_mcp_fallback_download",
                "source": source_name,
                "paper_id": paper_id,
                "doi": doi or "",
                "title": title or "",
                "use_scihub": bool(use_scihub),
                "mcp_probe": mcp_result["probe"],
                "mcp_server_probe": mcp_result["probe"],
                "downloaded_pdf": str(pdf_paths[0]),
                "upstream": {
                    "package": "paper-search-mcp",
                    "transport": "stdio",
                    "tool": "download_with_fallback",
                    "fallback_chain": list(OA_FALLBACK_CHAIN)
                    + (["scihub"] if use_scihub else []),
                    "use_scihub": bool(use_scihub),
                    "returncode": 0,
                    "raw_response": mcp_result.get("raw_response", {}),
                },
            }
        mcp_failure = {
            **mcp_result["probe"],
            "available": False,
            "error": "paper-search MCP fallback download produced no PDF",
            "raw_response": mcp_result.get("raw_response", {}),
            "fallback_chain": list(OA_FALLBACK_CHAIN) + (["scihub"] if use_scihub else []),
            "use_scihub": bool(use_scihub),
        }
        if stop_after_oa_fallback:
            return {
                "status": "failed",
                "mode": "paper_search_mcp_fallback_download",
                "source": source_name,
                "paper_id": paper_id,
                "doi": doi or "",
                "title": title or "",
                "use_scihub": bool(use_scihub),
                "mcp_probe": mcp_result["probe"],
                "mcp_server_probe": mcp_failure,
                "upstream": {
                    "package": "paper-search-mcp",
                    "transport": "stdio",
                    "tool": "download_with_fallback",
                    "fallback_chain": list(OA_FALLBACK_CHAIN)
                    + (["scihub"] if use_scihub else []),
                    "use_scihub": bool(use_scihub),
                    "returncode": None,
                    "raw_response": mcp_result.get("raw_response", {}),
                },
                "error": "paper-search OA fallback produced no PDF",
            }

    tool_name = f"download_{source_name}"
    try:
        mcp_result = _call_mcp_tool(
            tool_name,
            {"paper_id": paper_id, "save_path": str(output_dir)},
            timeout_seconds=timeout_seconds,
        )
    except MCPToolError as exc:
        mcp_failure = mcp_failure or _mcp_failure_payload(exc)
    else:
        pdf_paths = _downloaded_pdf_paths(output_dir)
        if pdf_paths:
            upstream_fallback = (
                {
                    "fallback_from": "paper_search_mcp_fallback_download",
                    "fallback_error": mcp_failure.get("error", "unavailable"),
                }
                if mcp_failure
                else {}
            )
            return {
                "status": "success",
                "mode": "paper_search_mcp_download",
                "source": source_name,
                "paper_id": paper_id,
                "mcp_probe": mcp_result["probe"],
                "mcp_server_probe": mcp_failure,
                "downloaded_pdf": str(pdf_paths[0]),
                "upstream": {
                    "package": "paper-search-mcp",
                    "transport": "stdio",
                    "tool": tool_name,
                    "returncode": 0,
                    "raw_response": mcp_result.get("raw_response", {}),
                    **upstream_fallback,
                },
            }
        mcp_failure = {
            **mcp_result["probe"],
            "available": False,
            "error": "paper-search MCP download produced no PDF",
            "raw_response": mcp_result.get("raw_response", {}),
        }
    selected_command = command or os.environ.get("PAPER_SOURCE_PAPER_SEARCH_COMMAND") or "paper-search"
    probe = probe_paper_search_mcp(selected_command)
    if not probe["available"]:
        return {
            "status": "failed",
            "mode": "paper_search_cli_download",
            "source": source_name,
            "paper_id": paper_id,
            "mcp_probe": probe,
            "mcp_server_probe": mcp_failure,
            "error": COMMAND_UNAVAILABLE,
        }
    resolved_command = probe["command"]
    args = ["download", source_name, paper_id, "--save-path", str(output_dir)]
    try:
        result = _run_command(resolved_command, args, timeout_seconds=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "failed",
            "mode": "paper_search_cli_download",
            "source": source_name,
            "paper_id": paper_id,
            "mcp_probe": probe,
            "mcp_server_probe": mcp_failure,
            "upstream": {
                "package": "paper-search-mcp",
                "cli_command": resolved_command,
                "returncode": None,
                "stdout": _timeout_text(exc.output).strip(),
                "stderr": _timeout_text(exc.stderr).strip(),
                "timeout_seconds": timeout_seconds,
                **_fallback_fields(mcp_failure),
            },
            "error": "paper-search download timed out",
        }
    pdf_paths = _downloaded_pdf_paths(output_dir)
    if result.returncode != 0:
        return {
            "status": "failed",
            "mode": "paper_search_cli_download",
            "source": source_name,
            "paper_id": paper_id,
            "mcp_probe": probe,
            "mcp_server_probe": mcp_failure,
            "upstream": {
                "package": "paper-search-mcp",
                "cli_command": resolved_command,
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                **_fallback_fields(mcp_failure),
            },
            "error": "paper-search download failed",
        }
    if not pdf_paths:
        return {
            "status": "failed",
            "mode": "paper_search_cli_download",
            "source": source_name,
            "paper_id": paper_id,
            "mcp_probe": probe,
            "mcp_server_probe": mcp_failure,
            "upstream": {
                "package": "paper-search-mcp",
                "cli_command": resolved_command,
                "returncode": result.returncode,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                **_fallback_fields(mcp_failure),
            },
            "error": "paper-search download produced no PDF",
        }
    return {
        "status": "success",
        "mode": "paper_search_cli_download",
        "source": source_name,
        "paper_id": paper_id,
        "mcp_probe": probe,
        "mcp_server_probe": mcp_failure,
        "downloaded_pdf": str(pdf_paths[0]),
        "upstream": {
            "package": "paper-search-mcp",
            "cli_command": resolved_command,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            **_fallback_fields(mcp_failure),
        },
    }


def read_paper_preview(
    *,
    source: str,
    paper_id: str,
    output_path: Path,
    save_dir: Path | None = None,
    command: str | None = None,
    timeout_seconds: int = 120,
) -> dict:
    apply_runtime_config()
    source_name = source.strip().lower().replace("-", "_")
    paper_id_text = str(paper_id or "").strip()
    tool_name = _paper_read_tool_name(source_name)
    if not source_name or not paper_id_text:
        return {
            "status": "skipped",
            "mode": "paper_search_mcp_read_preview",
            "source": source_name,
            "paper_id": paper_id_text,
            "tool": tool_name,
            "output_path": str(output_path),
            "authoritative": False,
            "replaces_mineru": False,
            "error": "source and paper_id are required",
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    preview_save_dir = save_dir or output_path.parent
    preview_save_dir.mkdir(parents=True, exist_ok=True)
    save_path = str(preview_save_dir)
    mcp_failure: dict | None = None
    try:
        mcp_result = _call_mcp_tool(
            tool_name,
            {"paper_id": paper_id_text, "save_path": save_path},
            timeout_seconds=timeout_seconds,
        )
    except MCPToolError as exc:
        mcp_failure = _mcp_failure_payload(exc)
    else:
        preview_text = _meaningful_preview_text(
            _extract_preview_text(mcp_result.get("payload"), mcp_result.get("raw_response"))
        )
        if preview_text:
            return {
                "status": "success",
                "mode": "paper_search_mcp_read_preview",
                "source": source_name,
                "paper_id": paper_id_text,
                "tool": tool_name,
                "mcp_probe": mcp_result["probe"],
                "upstream": {
                    "package": "paper-search-mcp",
                    "transport": "stdio",
                    "tool": tool_name,
                    "returncode": 0,
                },
                **_write_preview(output_path, preview_text),
            }
        mcp_failure = {
            **mcp_result["probe"],
            "available": False,
            "error": "paper-search MCP read preview produced no meaningful text",
        }

    selected_command = command or os.environ.get("PAPER_SOURCE_PAPER_SEARCH_COMMAND") or "paper-search"
    probe = probe_paper_search_mcp(selected_command)
    if not probe["available"]:
        return {
            "status": "failed",
            "mode": "paper_search_cli_read_preview",
            "source": source_name,
            "paper_id": paper_id_text,
            "tool": tool_name,
            "mcp_probe": probe,
            "mcp_server_probe": mcp_failure,
            "output_path": str(output_path),
            "authoritative": False,
            "replaces_mineru": False,
            "error": COMMAND_UNAVAILABLE,
        }
    resolved_command = probe["command"]
    args = ["read", source_name, paper_id_text, "--save-path", save_path]
    try:
        result = _run_command(resolved_command, args, timeout_seconds=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "failed",
            "mode": "paper_search_cli_read_preview",
            "source": source_name,
            "paper_id": paper_id_text,
            "tool": tool_name,
            "mcp_probe": probe,
            "mcp_server_probe": mcp_failure,
            "output_path": str(output_path),
            "authoritative": False,
            "replaces_mineru": False,
            "upstream": {
                "package": "paper-search-mcp",
                "cli_command": resolved_command,
                "returncode": None,
                "stdout_char_count": len(_timeout_text(exc.output).strip()),
                "stderr": _timeout_text(exc.stderr).strip(),
                "timeout_seconds": timeout_seconds,
                **_fallback_fields(mcp_failure),
            },
            "error": "paper-search read timed out",
        }
    preview_text = _meaningful_preview_text(result.stdout)
    if result.returncode != 0 or not preview_text:
        return {
            "status": "failed",
            "mode": "paper_search_cli_read_preview",
            "source": source_name,
            "paper_id": paper_id_text,
            "tool": tool_name,
            "mcp_probe": probe,
            "mcp_server_probe": mcp_failure,
            "output_path": str(output_path),
            "authoritative": False,
            "replaces_mineru": False,
            "upstream": {
                "package": "paper-search-mcp",
                "cli_command": resolved_command,
                "returncode": result.returncode,
                "stdout_char_count": len(preview_text),
                "stderr": result.stderr.strip(),
                **_fallback_fields(mcp_failure),
            },
            "error": "paper-search read failed" if result.returncode != 0 else "paper-search read produced no text",
        }
    return {
        "status": "success",
        "mode": "paper_search_cli_read_preview",
        "source": source_name,
        "paper_id": paper_id_text,
        "tool": tool_name,
        "mcp_probe": probe,
        "mcp_server_probe": mcp_failure,
        "upstream": {
            "package": "paper-search-mcp",
            "cli_command": resolved_command,
            "returncode": result.returncode,
            "stderr": result.stderr.strip(),
            **_fallback_fields(mcp_failure),
        },
        **_write_preview(output_path, preview_text),
    }
