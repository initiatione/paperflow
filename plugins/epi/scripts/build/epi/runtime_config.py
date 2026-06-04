from __future__ import annotations

import json
import os
import shlex
from pathlib import Path
from typing import Any


RUNTIME_CONFIG_ENV = "EPI_RUNTIME_CONFIG"
RUNTIME_CONFIG_SCHEMA = "epi-runtime-config-v1"


def _codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".codex"


def runtime_config_path() -> Path:
    configured = os.environ.get(RUNTIME_CONFIG_ENV)
    if configured:
        return Path(configured).expanduser()
    return _codex_home() / "plugins" / "paper-search" / "epi" / "runtime.json"


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


def _safe_env_key(key: str) -> bool:
    return key.startswith("EPI_") and key != RUNTIME_CONFIG_ENV


def _normalize_env_value(value: object) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value)
    return str(value)


def _runtime_secret_key(key: str) -> bool:
    return key in {"MINERU_TOKEN", "EASYSCHOLAR_SECRET_KEY"}


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


def _apply_runtime_payload(status: dict[str, Any], payload: dict[str, Any]) -> None:
    paper_search_mcp = payload.get("paper_search_mcp")
    if isinstance(paper_search_mcp, dict):
        command = paper_search_mcp.get("command")
        args = _as_args_string(paper_search_mcp.get("args"))
        if command:
            _set_env_if_missing(status, "EPI_PAPER_SEARCH_MCP_COMMAND", command)
        if args:
            _set_env_if_missing(status, "EPI_PAPER_SEARCH_MCP_ARGS", args)

    paper_search_cli = payload.get("paper_search_cli")
    if isinstance(paper_search_cli, dict) and paper_search_cli.get("command"):
        _set_env_if_missing(status, "EPI_PAPER_SEARCH_COMMAND", paper_search_cli["command"])

    mineru = payload.get("mineru")
    if isinstance(mineru, dict):
        if mineru.get("command"):
            _set_env_if_missing(status, "EPI_MINERU_COMMAND", mineru["command"])
        env_files = mineru.get("env_files")
        if env_files is None and mineru.get("env_file"):
            env_files = [mineru["env_file"]]
        if isinstance(env_files, (str, Path)):
            env_files = [env_files]
        if isinstance(env_files, list):
            for env_file in env_files:
                env_status = _load_env_file(Path(str(env_file)).expanduser())
                status["env_files"].append(env_status)
                status["applied_env"].extend(env_status["applied_env"])
                status["skipped_env"].extend(env_status["skipped_env"])
                status["warnings"].extend(env_status["warnings"])

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
        payload = json.loads(path.read_text(encoding="utf-8"))
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
    _apply_runtime_payload(status, payload)
    status["applied_env"] = sorted(set(status["applied_env"]))
    status["skipped_env"] = sorted(set(status["skipped_env"]))
    status["warnings"] = sorted(set(status["warnings"]))
    return status
