from __future__ import annotations

import json
import os
import webbrowser
from pathlib import Path

from epi.config import config_status
from epi.paper_search_adapter import probe_paper_search_mcp
from epi.run_mineru_parse import _command_tokens


REQUIRED_PATHS = [
    ".codex-plugin/plugin.json",
    "scripts/orchestrator.py",
    "scripts/build/epi",
    "build/mineru-paper-parser/mineru_batch_to_md.py",
    "skills/paper-discovery/SKILL.md",
    "skills/paper-ingest/SKILL.md",
    "skills/mineru-paper-parser",
    "templates/interests.example.yaml",
    "templates/routing-rules.example.yaml",
    "templates/wiki/manifest.json",
    "docs",
    "metric-packs/epi-quality-gates",
]

PAPER_SEARCH_SETUP_URL = "https://github.com/openags/paper-search-mcp"
MINERU_TOKEN_SETUP_URL = "https://mineru.net/apiManage/docs?openApplyModal=true"

SETUP_GUIDES = {
    "paper_search_cli": {
        "summary": "Configure paper-search CLI",
        "url": PAPER_SEARCH_SETUP_URL,
        "description": "Install the upstream CLI or point EPI_PAPER_SEARCH_COMMAND at a local wrapper.",
        "commands": [
            "uvx --from git+https://github.com/openags/paper-search-mcp.git paper-search --help",
            "$env:EPI_PAPER_SEARCH_COMMAND='D:\\paper-search\\.env\\paper-search-live.ps1'",
        ],
    },
    "mineru_token": {
        "summary": "Configure MINERU_TOKEN",
        "url": MINERU_TOKEN_SETUP_URL,
        "description": "Create a MinerU API token, then expose it to EPI as MINERU_TOKEN.",
        "commands": [
            "$env:MINERU_TOKEN='<your MinerU token>'",
            "[Environment]::SetEnvironmentVariable('MINERU_TOKEN', '<your MinerU token>', 'User')",
        ],
    },
}


def _check_path(plugin_root: Path, relative_path: str) -> dict:
    path = plugin_root / relative_path
    return {
        "name": relative_path,
        "status": "ok" if path.exists() else "error",
        "path": str(path),
        "message": "present" if path.exists() else "missing required plugin path",
    }


def _load_plugin_metadata(plugin_root: Path) -> tuple[dict, dict]:
    manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
    if not manifest_path.exists():
        return (
            {"name": "unknown", "version": "unknown"},
            {
                "name": "plugin_manifest",
                "status": "error",
                "path": str(manifest_path),
                "message": "missing plugin manifest",
            },
        )
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return (
            {"name": "unknown", "version": "unknown"},
            {
                "name": "plugin_manifest",
                "status": "error",
                "path": str(manifest_path),
                "message": f"invalid JSON: {exc}",
            },
        )
    return (
        {
            "name": payload.get("name", "unknown"),
            "version": payload.get("version", "unknown"),
            "display_name": payload.get("interface", {}).get("displayName"),
        },
        {
            "name": "plugin_manifest",
            "status": "ok",
            "path": str(manifest_path),
            "message": "loaded",
        },
    )


def _setup_guide(check_name: str) -> dict | None:
    guide = SETUP_GUIDES.get(check_name)
    if not guide:
        return None
    return {
        "summary": guide["summary"],
        "url": guide["url"],
        "description": guide["description"],
        "commands": list(guide["commands"]),
    }


def _with_setup(check: dict) -> dict:
    guide = _setup_guide(check["name"])
    if guide and check["status"] == "warning":
        return {**check, "setup": guide}
    return check


def _check_paper_search(command: str | None) -> dict:
    selected_command = command or os.environ.get("EPI_PAPER_SEARCH_COMMAND") or "paper-search"
    probe = probe_paper_search_mcp(selected_command)
    if probe.get("available"):
        return {
            "name": "paper_search_cli",
            "status": "ok",
            "command": probe.get("command", selected_command),
            "message": probe.get("stdout") or "available",
            "probe": probe,
        }
    return _with_setup(
        {
            "name": "paper_search_cli",
            "status": "warning",
            "command": selected_command,
            "message": probe.get("error", "unavailable"),
            "probe": probe,
        }
    )


def _check_mineru_command(plugin_root: Path, command: str | None) -> dict:
    tokens = _command_tokens(command, plugin_root)
    executable = tokens[0] if tokens else ""
    executable_path = Path(executable)
    available = executable_path.exists() or any(
        (Path(directory) / executable).exists()
        for directory in os.environ.get("PATH", "").split(os.pathsep)
        if directory
    )
    return {
        "name": "mineru_command",
        "status": "ok" if available else "warning",
        "command": tokens,
        "message": "available" if available else "not found until configured or installed",
    }


def _check_mineru_token() -> dict:
    token_present = bool(os.environ.get("MINERU_TOKEN"))
    return _with_setup(
        {
            "name": "mineru_token",
            "status": "ok" if token_present else "warning",
            "message": "MINERU_TOKEN is set" if token_present else "MINERU_TOKEN is not set",
        }
    )


def _check_epi_config(vault_path: Path) -> dict:
    status = config_status(vault_path)
    configured = bool(status["configured"])
    return {
        "name": "epi_config",
        "status": "ok" if configured else "warning",
        "message": "initialized" if configured else "not initialized; run config-status and init-config before paper workflows",
        "configured": configured,
        "needs_onboarding": bool(status["needs_onboarding"]),
        "config_path": status["config_path"],
        "state_path": status["state_path"],
        "history_dir": status["history_dir"],
    }


def setup_links_for_report(report: dict) -> list[dict]:
    links = []
    seen_urls = set()
    for check in report.get("checks", []):
        setup = check.get("setup")
        if not setup:
            continue
        url = setup["url"]
        if url in seen_urls:
            continue
        seen_urls.add(url)
        links.append({"name": check["name"], "summary": setup["summary"], "url": url})
    return links


def open_setup_links(report: dict) -> list[str]:
    opened_urls = []
    for link in setup_links_for_report(report):
        url = link["url"]
        webbrowser.open(url)
        opened_urls.append(url)
    return opened_urls


def collect_doctor_report(
    *,
    plugin_root: Path,
    vault_path: Path,
    paper_search_command: str | None,
    mineru_command: str | None = None,
) -> dict:
    plugin_root = plugin_root.resolve()
    vault_path = vault_path.resolve()
    plugin_metadata, manifest_check = _load_plugin_metadata(plugin_root)
    checks = [manifest_check]
    checks.extend(_check_path(plugin_root, relative_path) for relative_path in REQUIRED_PATHS if relative_path != ".codex-plugin/plugin.json")
    checks.append(_check_epi_config(vault_path))
    checks.append(_check_paper_search(paper_search_command))
    checks.append(_check_mineru_command(plugin_root, mineru_command))
    checks.append(_check_mineru_token())
    overall_status = "error" if any(check["status"] == "error" for check in checks) else "ok"
    report = {
        "overall_status": overall_status,
        "plugin_root": str(plugin_root),
        "plugin": plugin_metadata,
        "default_vault": str(vault_path),
        "checks": checks,
    }
    setup_links = setup_links_for_report(report)
    report["setup_required"] = bool(setup_links)
    report["setup_links"] = setup_links
    return report


def render_doctor_report(report: dict) -> str:
    plugin = report["plugin"]
    lines = [
        "EPI Doctor",
        f"overall_status={report['overall_status']}",
        f"plugin_name={plugin.get('name', 'unknown')}",
        f"plugin_version={plugin.get('version', 'unknown')}",
        f"plugin_root={report['plugin_root']}",
        f"default_vault={report['default_vault']}",
        "",
        "Checks:",
    ]
    for check in report["checks"]:
        lines.append(f"- {check['name']}: {check['status']} - {check.get('message', '')}")
    if report.get("setup_required"):
        lines.extend(["", "First-use setup:"])
        for check in report["checks"]:
            setup = check.get("setup")
            if not setup:
                continue
            lines.append(f"- {check['name']}: {setup['summary']}")
            lines.append(f"  url: {setup['url']}")
            lines.append(f"  note: {setup['description']}")
            if setup.get("commands"):
                lines.append("  commands:")
                lines.extend(f"    - {command}" for command in setup["commands"])
        lines.append("  Run doctor --open-setup to open these setup pages in your browser.")
    if report.get("opened_setup_urls"):
        lines.extend(["", "Opened setup pages:"])
        lines.extend(f"- {url}" for url in report["opened_setup_urls"])
    lines.append("")
    return "\n".join(lines)
