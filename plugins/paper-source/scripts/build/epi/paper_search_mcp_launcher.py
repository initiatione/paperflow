from __future__ import annotations

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

from epi.runtime_config import apply_runtime_config


def _missing_or_empty(key: str) -> bool:
    return not os.environ.get(key)


def _drop_empty_provider_env() -> None:
    # Plugin .mcp.json may provide empty placeholders; runtime env files must be
    # allowed to fill them with real values.
    for key in [
        "PAPER_SEARCH_MCP_UNPAYWALL_EMAIL",
        "UNPAYWALL_EMAIL",
        "PAPER_SEARCH_MCP_CORE_API_KEY",
        "CORE_API_KEY",
        "PAPER_SEARCH_MCP_SEMANTIC_SCHOLAR_API_KEY",
        "SEMANTIC_SCHOLAR_API_KEY",
        "PAPER_SEARCH_MCP_DOAJ_API_KEY",
        "DOAJ_API_KEY",
        "PAPER_SEARCH_MCP_ZENODO_ACCESS_TOKEN",
        "ZENODO_ACCESS_TOKEN",
        "PAPER_SEARCH_MCP_GOOGLE_SCHOLAR_PROXY_URL",
        "GOOGLE_SCHOLAR_PROXY_URL",
    ]:
        if _missing_or_empty(key):
            os.environ.pop(key, None)


def build_launch_command() -> list[str]:
    _drop_empty_provider_env()
    apply_runtime_config()
    command = os.environ.get("EPI_PAPER_SEARCH_MCP_COMMAND") or "python"
    args = shlex.split(os.environ.get("EPI_PAPER_SEARCH_MCP_ARGS") or "-m paper_search_mcp.server")
    if _should_autodetect_python(command, args):
        selected = _select_paper_search_python(command)
        if selected is None:
            raise RuntimeError(_missing_paper_search_mcp_message())
        command = selected
    return [command, *args]


def _should_autodetect_python(command: str, args: list[str]) -> bool:
    return _is_python_command(command) and _is_paper_search_mcp_server_args(args)


def _is_paper_search_mcp_server_args(args: list[str]) -> bool:
    return args[:2] == ["-m", "paper_search_mcp.server"]


def _is_python_command(command: str) -> bool:
    command_name = command.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return command_name in {"python", "python.exe", "python3", "python3.exe"}


def _is_unqualified_python_command(command: str) -> bool:
    return command.lower() in {"python", "python.exe", "python3", "python3.exe"}


def _select_paper_search_python(configured_command: str) -> str | None:
    for candidate in _candidate_python_commands(configured_command):
        if _python_can_import_paper_search_mcp(candidate):
            return candidate
    return None


def _missing_paper_search_mcp_message() -> str:
    runtime_path = os.environ.get("EPI_RUNTIME_CONFIG") or "<CODEX_HOME>/plugins/paperflow/paper-source/runtime.json"
    return (
        "paper-search-mcp launcher could not find a Python interpreter that can import "
        "paper_search_mcp. Install paper-search-mcp into a Python environment, or set "
        "paper_search_mcp.command in runtime.json / EPI_PAPER_SEARCH_MCP_COMMAND to the "
        f"interpreter that provides it. Runtime config path: {runtime_path}"
    )


def _candidate_python_commands(configured_command: str) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def add(command: str | os.PathLike[str] | None) -> None:
        if not command:
            return
        text = str(command)
        key = os.path.normcase(os.path.abspath(text)) if _looks_like_path(text) else text.lower()
        if key in seen:
            return
        seen.add(key)
        candidates.append(text)

    add(_resolve_command_path(configured_command))
    add(sys.executable)
    for command in _path_python_commands():
        add(command)
    for command in _conda_python_commands():
        add(command)
    return candidates


def _looks_like_path(command: str) -> bool:
    return any(separator in command for separator in ("/", "\\")) or bool(Path(command).drive)


def _resolve_command_path(command: str) -> str:
    if _looks_like_path(command):
        return command
    return shutil.which(command) or command


def _path_python_commands() -> list[str]:
    commands: list[str] = []
    for path_entry in os.environ.get("PATH", "").split(os.pathsep):
        if not path_entry:
            continue
        directory = Path(path_entry)
        for name in ("python.exe", "python", "python3.exe", "python3"):
            candidate = directory / name
            if candidate.exists():
                commands.append(str(candidate))
    return commands


def _conda_python_commands() -> list[str]:
    commands: list[str] = []

    def add_prefix(prefix: str | os.PathLike[str] | None) -> None:
        if not prefix:
            return
        candidate = Path(prefix) / "python.exe"
        if candidate.exists():
            commands.append(str(candidate))

    add_prefix(os.environ.get("CONDA_PREFIX"))

    conda_roots: list[Path] = []
    conda_exe = os.environ.get("CONDA_EXE")
    if conda_exe:
        conda_roots.append(Path(conda_exe).resolve().parent.parent)
    executable_path = Path(sys.executable).resolve()
    parts = [part.lower() for part in executable_path.parts]
    if "envs" in parts:
        envs_index = parts.index("envs")
        conda_roots.append(Path(*executable_path.parts[:envs_index]))
    else:
        conda_roots.append(executable_path.parent)

    for root in conda_roots:
        add_prefix(root)
        envs_root = root / "envs"
        if envs_root.exists():
            for env_python in envs_root.glob("*/python.exe"):
                commands.append(str(env_python))
    return commands


def _python_can_import_paper_search_mcp(command: str) -> bool:
    try:
        result = subprocess.run(
            [command, "-c", "import paper_search_mcp"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def main() -> int:
    try:
        command = build_launch_command()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    try:
        process = subprocess.run(command)
    except OSError as exc:
        print(f"paper-search-mcp launcher could not start command {command!r}: {exc}", file=sys.stderr)
        return 1
    return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())
