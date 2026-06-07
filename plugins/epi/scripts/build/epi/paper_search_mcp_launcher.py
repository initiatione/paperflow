from __future__ import annotations

import os
import shlex
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
    return [command, *args]


def main() -> int:
    process = subprocess.run(build_launch_command())
    return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())
