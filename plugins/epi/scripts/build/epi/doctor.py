from __future__ import annotations

import json
import os
from pathlib import Path

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


def _check_paper_search(command: str) -> dict:
    probe = probe_paper_search_mcp(command)
    if probe.get("available"):
        return {
            "name": "paper_search_cli",
            "status": "ok",
            "command": probe.get("command", command),
            "message": probe.get("stdout") or "available",
            "probe": probe,
        }
    return {
        "name": "paper_search_cli",
        "status": "warning",
        "command": command,
        "message": probe.get("error", "unavailable"),
        "probe": probe,
    }


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
    return {
        "name": "mineru_token",
        "status": "ok" if token_present else "warning",
        "message": "MINERU_TOKEN is set" if token_present else "MINERU_TOKEN is not set",
    }


def collect_doctor_report(
    *,
    plugin_root: Path,
    vault_path: Path,
    paper_search_command: str,
    mineru_command: str | None = None,
) -> dict:
    plugin_root = plugin_root.resolve()
    vault_path = vault_path.resolve()
    plugin_metadata, manifest_check = _load_plugin_metadata(plugin_root)
    checks = [manifest_check]
    checks.extend(_check_path(plugin_root, relative_path) for relative_path in REQUIRED_PATHS if relative_path != ".codex-plugin/plugin.json")
    checks.append(_check_paper_search(paper_search_command))
    checks.append(_check_mineru_command(plugin_root, mineru_command))
    checks.append(_check_mineru_token())
    overall_status = "error" if any(check["status"] == "error" for check in checks) else "ok"
    return {
        "overall_status": overall_status,
        "plugin_root": str(plugin_root),
        "plugin": plugin_metadata,
        "default_vault": str(vault_path),
        "checks": checks,
    }


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
    lines.append("")
    return "\n".join(lines)
