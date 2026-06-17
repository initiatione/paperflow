from __future__ import annotations

import json
import os
import shlex
from pathlib import Path
from typing import Any

from paper_source.artifacts import read_json


RUNTIME_CONFIG_ENV = "PAPER_SOURCE_RUNTIME_CONFIG"
RUNTIME_CONFIG_SCHEMA = "paper-source-runtime-config-v1"
PAPER_SEARCH_PROVIDER_ENV_KEYS = {
    "PAPER_SEARCH_MCP_UNPAYWALL_EMAIL",
    "UNPAYWALL_EMAIL",
    "PAPER_SEARCH_MCP_CORE_API_KEY",
    "CORE_API_KEY",
    "PAPER_SEARCH_MCP_SEMANTIC_SCHOLAR_API_KEY",
    "SEMANTIC_SCHOLAR_API_KEY",
    "PAPER_SEARCH_MCP_GOOGLE_SCHOLAR_PROXY_URL",
    "GOOGLE_SCHOLAR_PROXY_URL",
    "PAPER_SEARCH_MCP_DOAJ_API_KEY",
    "DOAJ_API_KEY",
    "PAPER_SEARCH_MCP_ZENODO_ACCESS_TOKEN",
    "ZENODO_ACCESS_TOKEN",
}
GROK_SEARCH_PROVIDER_ENV_KEYS = {
    "OPENAI_COMPATIBLE_API_URL",
    "OPENAI_COMPATIBLE_API_KEY",
    "OPENAI_COMPATIBLE_MODEL",
    "OPENAI_API_KEY",
    "XAI_API_KEY",
    "GROK_API_KEY",
    "GROK_SEARCH_API_KEY",
    "GROK_SEARCH_WEB_SEARCH",
    "GROK_SEARCH_TIMEOUT_SECONDS",
    "TAVILY_API_KEY",
    "FIRECRAWL_API_KEY",
    "BRAVE_API_KEY",
    "SERPAPI_API_KEY",
}


def _codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".codex"


def runtime_config_path() -> Path:
    configured = os.environ.get(RUNTIME_CONFIG_ENV)
    if configured:
        return Path(configured).expanduser()
    return _codex_home() / "plugins" / "paperflow" / "paper-source" / "runtime.json"


def _empty_status(path: Path) -> dict[str, Any]:
    return {
        "schema_version": RUNTIME_CONFIG_SCHEMA,
        "path": str(path),
        "loaded": False,
        "applied_env": [],
        "skipped_env": [],
        "env_files": [],
        "warnings": [],
    }


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _standard_runtime_root() -> Path:
    return _codex_home() / "plugins" / "paperflow" / "paper-source"


def _looks_like_path(value: str) -> bool:
    return any(separator in value for separator in ("/", "\\")) or bool(Path(value).drive)


def _has_git_parent(path: Path) -> bool:
    current = path if path.is_dir() else path.parent
    try:
        current = current.resolve()
    except OSError:
        current = current.absolute()
    for parent in (current, *current.parents):
        if (parent / ".git").exists():
            return True
    return False


def _path_from_runtime_value(value: object) -> Path | None:
    if not isinstance(value, str) or not value.strip() or not _looks_like_path(value):
        return None
    return Path(value).expanduser()


def _runtime_path_issue(
    *,
    issues: list[dict[str, Any]],
    section: str,
    field: str,
    path: Path,
    code: str,
    message: str,
) -> None:
    issues.append(
        {
            "section": section,
            "field": field,
            "path": str(path),
            "code": code,
            "severity": "warning",
            "message": message,
        }
    )


def _check_runtime_env_file_path(
    *,
    issues: list[dict[str, Any]],
    runtime_root: Path,
    policy_active: bool,
    section: str,
    field: str,
    value: object,
) -> None:
    path = _path_from_runtime_value(value)
    if path is None:
        return
    if policy_active and not _is_relative_to(path, runtime_root):
        _runtime_path_issue(
            issues=issues,
            section=section,
            field=field,
            path=path,
            code="runtime_env_file_outside_user_plugin_runtime",
            message=(
                "runtime env_file should live under the user-level Paper Source runtime directory; "
                "copy provider env files into %USERPROFILE%\\.codex\\plugins\\paperflow\\paper-source"
            ),
        )
    if policy_active and _has_git_parent(path) and not _is_relative_to(path, _codex_home()):
        _runtime_path_issue(
            issues=issues,
            section=section,
            field=field,
            path=path,
            code="runtime_env_file_points_to_development_checkout",
            message="runtime env_file points into a development checkout; installed-user runtime must not depend on source trees",
        )


def _runtime_path_policy(payload: dict[str, Any], runtime_path: Path) -> dict[str, Any]:
    runtime_root = runtime_path.parent
    standard_root = _standard_runtime_root()
    policy_active = _is_relative_to(runtime_path, standard_root)
    issues: list[dict[str, Any]] = []
    sections = {
        "paper_search_mcp": payload.get("paper_search_mcp"),
        "grok_search_mcp": payload.get("grok_search_mcp"),
        "paper_search_cli": payload.get("paper_search_cli"),
        "mineru": payload.get("mineru"),
        "easyscholar": payload.get("easyscholar"),
    }
    for section_name, section in sections.items():
        if not isinstance(section, dict):
            continue
        _check_runtime_env_file_path(
            issues=issues,
            runtime_root=runtime_root,
            policy_active=policy_active,
            section=section_name,
            field="env_file",
            value=section.get("env_file"),
        )
        env_files = section.get("env_files")
        if isinstance(env_files, list):
            for index, item in enumerate(env_files):
                _check_runtime_env_file_path(
                    issues=issues,
                    runtime_root=runtime_root,
                    policy_active=policy_active,
                    section=section_name,
                    field=f"env_files[{index}]",
                    value=item,
                )
        command_path = _path_from_runtime_value(section.get("command"))
        if command_path is None:
            continue
        if ".env" in {part.lower() for part in command_path.parts}:
            _runtime_path_issue(
                issues=issues,
                section=section_name,
                field="command",
                path=command_path,
                code="runtime_command_points_to_env_helper",
                message="runtime command should be an installed executable or wrapper, not a project .env helper script",
            )
        if policy_active and _has_git_parent(command_path) and not _is_relative_to(command_path, _codex_home()):
            _runtime_path_issue(
                issues=issues,
                section=section_name,
                field="command",
                path=command_path,
                code="runtime_command_points_to_development_checkout",
                message="runtime command points into a development checkout; use PATH, a global install, or the user-level plugin runtime directory",
            )
    return {
        "schema_version": "paper-source-runtime-path-policy-v1",
        "active": policy_active,
        "runtime_root": str(runtime_root),
        "standard_runtime_root": str(standard_root),
        "allowed_env_file_root": str(runtime_root),
        "issues": issues,
    }


def _safe_env_key(key: str) -> bool:
    return (
        (key.startswith("PAPER_SOURCE_") and key != RUNTIME_CONFIG_ENV)
        or key in PAPER_SEARCH_PROVIDER_ENV_KEYS
        or key in GROK_SEARCH_PROVIDER_ENV_KEYS
    )


def _normalize_env_value(value: object) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    return str(value)


def _runtime_secret_key(key: str) -> bool:
    return key in {
        "MINERU_TOKEN",
        "EASYSCHOLAR_SECRET_KEY",
        "PAPER_SEARCH_MCP_UNPAYWALL_EMAIL",
        "UNPAYWALL_EMAIL",
        "PAPER_SEARCH_MCP_CORE_API_KEY",
        "CORE_API_KEY",
        "PAPER_SEARCH_MCP_SEMANTIC_SCHOLAR_API_KEY",
        "SEMANTIC_SCHOLAR_API_KEY",
        "PAPER_SEARCH_MCP_GOOGLE_SCHOLAR_PROXY_URL",
        "GOOGLE_SCHOLAR_PROXY_URL",
        "PAPER_SEARCH_MCP_DOAJ_API_KEY",
        "DOAJ_API_KEY",
        "PAPER_SEARCH_MCP_ZENODO_ACCESS_TOKEN",
        "ZENODO_ACCESS_TOKEN",
        "OPENAI_COMPATIBLE_API_KEY",
        "OPENAI_API_KEY",
        "XAI_API_KEY",
        "GROK_API_KEY",
        "GROK_SEARCH_API_KEY",
        "TAVILY_API_KEY",
        "FIRECRAWL_API_KEY",
        "BRAVE_API_KEY",
        "SERPAPI_API_KEY",
    }


def _set_env_if_missing(status: dict[str, Any], key: str, value: object) -> None:
    if not key:
        return
    if _runtime_secret_key(key):
        status["warnings"].append(f"{key} in runtime.json ignored; use an env_file")
        status["skipped_env"].append(key)
        return
    if not _safe_env_key(key):
        status["warnings"].append(f"unsupported runtime env key ignored: {key}")
        status["skipped_env"].append(key)
        return
    if key in os.environ:
        status["skipped_env"].append(key)
        return
    os.environ[key] = _normalize_env_value(value)
    status["applied_env"].append(key)


def _set_env_from_env_file(status: dict[str, Any], key: str, value: str) -> None:
    if not key:
        return
    if not _runtime_secret_key(key) and not _safe_env_key(key):
        status["warnings"].append(f"unsupported env-file key ignored: {key}")
        status["skipped_env"].append(key)
        return
    if key in os.environ:
        status["skipped_env"].append(key)
        return
    os.environ[key] = value
    status["applied_env"].append(key)


def _load_env_file(path: Path) -> dict[str, Any]:
    status = {
        "path": str(path),
        "loaded": False,
        "applied_env": [],
        "skipped_env": [],
        "warnings": [],
    }
    if not path.exists():
        status["warnings"].append("env file missing")
        return status
    status["loaded"] = True
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        _set_env_from_env_file(status, key, value)
    return status


def _as_args_string(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(shlex.quote(str(item)) for item in value)
    return str(value)


def _env_files_from_section(section: dict[str, Any]) -> list[object]:
    env_files = section.get("env_files")
    if env_files is None and section.get("env_file"):
        env_files = [section["env_file"]]
    if isinstance(env_files, (str, Path)):
        return [env_files]
    if isinstance(env_files, list):
        return list(env_files)
    return []


def _apply_env_file_section(status: dict[str, Any], section: dict[str, Any]) -> None:
    for env_file in _env_files_from_section(section):
        env_status = _load_env_file(Path(str(env_file)).expanduser())
        status["env_files"].append(env_status)
        status["applied_env"].extend(env_status["applied_env"])
        status["skipped_env"].extend(env_status["skipped_env"])
        status["warnings"].extend(env_status["warnings"])


def _apply_runtime_payload(status: dict[str, Any], payload: dict[str, Any]) -> None:
    paper_search_mcp = payload.get("paper_search_mcp")
    if isinstance(paper_search_mcp, dict):
        command = paper_search_mcp.get("command")
        args = _as_args_string(paper_search_mcp.get("args"))
        if command:
            _set_env_if_missing(status, "PAPER_SOURCE_PAPER_SEARCH_MCP_COMMAND", command)
        if args:
            _set_env_if_missing(status, "PAPER_SOURCE_PAPER_SEARCH_MCP_ARGS", args)
        _apply_env_file_section(status, paper_search_mcp)

    grok_search_mcp = payload.get("grok_search_mcp")
    if isinstance(grok_search_mcp, dict):
        command = grok_search_mcp.get("command")
        args = _as_args_string(grok_search_mcp.get("args"))
        if command:
            _set_env_if_missing(status, "PAPER_SOURCE_GROK_SEARCH_MCP_COMMAND", command)
        if args:
            _set_env_if_missing(status, "PAPER_SOURCE_GROK_SEARCH_MCP_ARGS", args)
        _apply_env_file_section(status, grok_search_mcp)

    paper_search_cli = payload.get("paper_search_cli")
    if isinstance(paper_search_cli, dict) and paper_search_cli.get("command"):
        _set_env_if_missing(status, "PAPER_SOURCE_PAPER_SEARCH_COMMAND", paper_search_cli["command"])

    mineru = payload.get("mineru")
    if isinstance(mineru, dict):
        if mineru.get("command"):
            _set_env_if_missing(status, "PAPER_SOURCE_MINERU_COMMAND", mineru["command"])
        _apply_env_file_section(status, mineru)

    easyscholar = payload.get("easyscholar")
    if isinstance(easyscholar, dict):
        _apply_env_file_section(status, easyscholar)

    env_payload = payload.get("env")
    if isinstance(env_payload, dict):
        for key, value in env_payload.items():
            _set_env_if_missing(status, str(key), value)


def apply_runtime_config() -> dict[str, Any]:
    path = runtime_config_path()
    status = _empty_status(path)
    if not path.exists():
        return status
    try:
        payload = read_json(path)
    except json.JSONDecodeError as exc:
        status["warnings"].append(f"invalid runtime config JSON: {exc}")
        return status
    if not isinstance(payload, dict):
        status["warnings"].append("runtime config must be a JSON object")
        return status
    status["loaded"] = True
    schema_version = payload.get("schema_version")
    if schema_version and schema_version != RUNTIME_CONFIG_SCHEMA:
        status["warnings"].append(f"unexpected runtime config schema_version: {schema_version}")
    path_policy = _runtime_path_policy(payload, path)
    status["path_policy"] = path_policy
    for issue in path_policy["issues"]:
        status["warnings"].append(f"{issue['code']}: {issue['section']}.{issue['field']} -> {issue['path']}")
    _apply_runtime_payload(status, payload)
    status["applied_env"] = sorted(set(status["applied_env"]))
    status["skipped_env"] = sorted(set(status["skipped_env"]))
    status["warnings"] = sorted(set(status["warnings"]))
    return status
