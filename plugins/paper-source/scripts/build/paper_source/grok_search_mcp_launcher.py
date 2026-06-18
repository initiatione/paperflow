from __future__ import annotations

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

from paper_source.runtime_config import apply_runtime_config


DEFAULT_GROK_SEARCH_COMMAND = "grok-search-rs"


def _split_command_line(command_line: str) -> list[str]:
    return [token.strip("\"'") for token in shlex.split(command_line, posix=False)]


def _looks_like_path(command: str) -> bool:
    return any(separator in command for separator in ("/", "\\")) or bool(Path(command).drive)


def _resolve_command(command: str) -> str | None:
    command_path = Path(command).expanduser()
    if _looks_like_path(command) and command_path.exists():
        return str(command_path)
    return shutil.which(command)


def build_launch_command() -> list[str]:
    apply_runtime_config()
    configured = os.environ.get("PAPER_SOURCE_GROK_SEARCH_MCP_COMMAND") or DEFAULT_GROK_SEARCH_COMMAND
    tokens = _split_command_line(configured)
    extra_args = os.environ.get("PAPER_SOURCE_GROK_SEARCH_MCP_ARGS")
    if extra_args:
        tokens.extend(_split_command_line(extra_args))
    if not tokens:
        raise RuntimeError(_missing_grok_search_mcp_message(DEFAULT_GROK_SEARCH_COMMAND))
    resolved = _resolve_command(tokens[0])
    if not resolved:
        raise RuntimeError(_missing_grok_search_mcp_message(tokens[0]))
    return [resolved, *tokens[1:]]


def _missing_grok_search_mcp_message(command: str) -> str:
    runtime_path = (
        os.environ.get("PAPER_SOURCE_RUNTIME_CONFIG")
        or "<CODEX_HOME>/plugins/paperflow/paper-source/runtime.json"
    )
    return (
        "grok-search-rs MCP launcher could not find command "
        f"{command!r}. Install grok-search-rs, put it on PATH, or set "
        "grok_search_mcp.command in runtime.json / PAPER_SOURCE_GROK_SEARCH_MCP_COMMAND. "
        f"Runtime config path: {runtime_path}"
    )


def main() -> int:
    try:
        command = build_launch_command()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    try:
        process = subprocess.run(command)
    except OSError as exc:
        print(f"grok-search-rs MCP launcher could not start command {command!r}: {exc}", file=sys.stderr)
        return 1
    return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())
