from __future__ import annotations

import json
import os
import re
import shutil
import webbrowser
from pathlib import Path

from epi.config import config_status
from epi.paper_search_adapter import paper_search_provider_readiness
from epi.paper_search_adapter import paper_search_source_capabilities
from epi.paper_search_adapter import probe_paper_search_mcp
from epi.paper_search_adapter import probe_paper_search_mcp_server
from epi.run_mineru_parse import _command_tokens
from epi.runtime_config import apply_runtime_config


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
EASYSCHOLAR_SETUP_URL = "https://www.easyscholar.cc"

SETUP_GUIDES = {
    "paper_search_mcp": {
        "summary": "Configure paper-search MCP server",
        "url": PAPER_SEARCH_SETUP_URL,
        "description": "Install the upstream MCP server or point EPI_PAPER_SEARCH_MCP_COMMAND at a local wrapper.",
        "commands": [
            "python -m paper_search_mcp.server",
            "$env:EPI_PAPER_SEARCH_MCP_COMMAND='python'",
            "$env:EPI_PAPER_SEARCH_MCP_ARGS='-m paper_search_mcp.server'",
        ],
    },
    "paper_search_cli": {
        "summary": "Configure paper-search CLI",
        "url": PAPER_SEARCH_SETUP_URL,
        "description": "Install the upstream CLI or point EPI_PAPER_SEARCH_COMMAND at a local wrapper for fallback.",
        "commands": [
            "uvx --from git+https://github.com/openags/paper-search-mcp.git paper-search --help",
            "$env:EPI_PAPER_SEARCH_COMMAND='<path-to-paper-search-wrapper>'",
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
    "easyscholar": {
        "summary": "Configure EASYSCHOLAR_SECRET_KEY",
        "url": EASYSCHOLAR_SETUP_URL,
        "description": "Create an EasyScholar secret key for default-on venue quality enrichment.",
        "commands": [
            "$env:EASYSCHOLAR_SECRET_KEY='<your EasyScholar secret key>'",
            "[Environment]::SetEnvironmentVariable('EASYSCHOLAR_SECRET_KEY', '<your EasyScholar secret key>', 'User')",
        ],
    },
}

MCP_SECTION_PATTERN = re.compile(
    r"""^\s*\[\s*mcp_servers\s*\.\s*(?:"paper-search-mcp"|'paper-search-mcp'|paper-search-mcp)\s*\]\s*$"""
)


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


def _check_paper_search_mcp_server() -> dict:
    probe = probe_paper_search_mcp_server(timeout_seconds=5)
    if probe.get("available"):
        return {
            "name": "paper_search_mcp",
            "status": "ok",
            "command": [probe.get("command"), *probe.get("args", [])],
            "message": "stdio server available",
            "probe": probe,
        }
    return _with_setup(
        {
            "name": "paper_search_mcp",
            "status": "warning",
            "command": [probe.get("command"), *probe.get("args", [])],
            "message": probe.get("error", "unavailable"),
            "probe": probe,
        }
    )


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


def _check_easyscholar() -> dict:
    key_present = bool(os.environ.get("EASYSCHOLAR_SECRET_KEY"))
    return _with_setup(
        {
            "name": "easyscholar",
            "status": "ok" if key_present else "warning",
            "secret_key": "set" if key_present else "missing",
            "message": "EASYSCHOLAR_SECRET_KEY is set"
            if key_present
            else "EASYSCHOLAR_SECRET_KEY is not set; EasyScholar enrichment will soft-fail as unverified",
        }
    )


def _check_paper_search_provider_readiness() -> dict:
    providers = paper_search_provider_readiness()
    actionable = [
        provider
        for provider, state in providers.items()
        if str(state.get("status", "")).startswith("missing_required")
        or str(state.get("status", "")).startswith("missing_recommended")
    ]
    return {
        "name": "paper_search_provider_readiness",
        "status": "warning" if actionable else "ok",
        "message": (
            "optional paper-search provider env gaps may limit OA fallback or source stability"
            if actionable
            else "paper-search provider env readiness checked"
        ),
        "providers": providers,
        "capabilities": paper_search_source_capabilities(),
    }


def _codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".codex"


def _check_codex_mcp_registration() -> dict:
    config_path = _codex_home() / "config.toml"
    if not config_path.exists():
        return {
            "name": "codex_mcp_registration",
            "status": "ok",
            "path": str(config_path),
            "message": "Codex config.toml not present; plugin .mcp.json self-registration is not shadowed here",
            "shadowing_static_config": False,
        }
    try:
        lines = config_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return {
            "name": "codex_mcp_registration",
            "status": "warning",
            "path": str(config_path),
            "message": f"could not read Codex config.toml to check paper-search-mcp registration: {exc}",
            "shadowing_static_config": None,
        }
    for line_number, line in enumerate(lines, start=1):
        if MCP_SECTION_PATTERN.match(line):
            return {
                "name": "codex_mcp_registration",
                "status": "warning",
                "path": str(config_path),
                "line": line_number,
                "message": (
                    "user-level [mcp_servers.paper-search-mcp] can shadow the Paper Source plugin .mcp.json "
                    "self-registration; remove that static block unless intentionally overriding the plugin"
                ),
                "shadowing_static_config": True,
            }
    return {
        "name": "codex_mcp_registration",
        "status": "ok",
        "path": str(config_path),
        "message": "no user-level paper-search-mcp static registration found",
        "shadowing_static_config": False,
    }


def _expand_plugin_path(plugin_root: Path, value: str) -> Path:
    expanded = value.replace("${CLAUDE_PLUGIN_ROOT}", str(plugin_root))
    return Path(expanded).expanduser()


def _looks_like_path(value: str) -> bool:
    return any(separator in value for separator in ("/", "\\")) or bool(Path(value).drive)


def _outer_command_available(plugin_root: Path, command: str) -> bool:
    if not command:
        return False
    if _looks_like_path(command) or "${CLAUDE_PLUGIN_ROOT}" in command:
        return _expand_plugin_path(plugin_root, command).exists()
    return shutil.which(command) is not None


def _launcher_script_from_args(plugin_root: Path, args: list[object]) -> Path | None:
    for arg in args:
        text = str(arg)
        if "paper_search_mcp_launcher.py" in text:
            return _expand_plugin_path(plugin_root, text)
    return None


def _check_mcp_outer_launcher(plugin_root: Path) -> dict:
    mcp_path = plugin_root / ".mcp.json"
    if not mcp_path.exists():
        return {
            "name": "mcp_outer_launcher",
            "status": "warning",
            "path": str(mcp_path),
            "server": "paper-search-mcp",
            "error": "plugin_mcp_json_missing",
            "message": "plugin .mcp.json is missing; paper-search-mcp self-registration will not be installed",
        }
    try:
        payload = json.loads(mcp_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "name": "mcp_outer_launcher",
            "status": "warning",
            "path": str(mcp_path),
            "server": "paper-search-mcp",
            "error": "plugin_mcp_json_unreadable",
            "message": f"plugin .mcp.json could not be read: {exc}",
        }
    servers = payload.get("mcpServers") if isinstance(payload, dict) else None
    server = servers.get("paper-search-mcp") if isinstance(servers, dict) else None
    if not isinstance(server, dict):
        return {
            "name": "mcp_outer_launcher",
            "status": "warning",
            "path": str(mcp_path),
            "server": "paper-search-mcp",
            "error": "paper_search_mcp_registration_missing",
            "message": "plugin .mcp.json does not register paper-search-mcp",
        }
    command = str(server.get("command") or "")
    raw_args = server.get("args")
    args = raw_args if isinstance(raw_args, list) else []
    launcher_script = _launcher_script_from_args(plugin_root, args)
    launcher_script_exists = bool(launcher_script and launcher_script.exists())
    command_available = _outer_command_available(plugin_root, command)
    error = None
    if not command_available:
        error = "outer_command_not_found"
    elif not launcher_script_exists:
        error = "launcher_script_not_found"
    status = "warning" if error else "ok"
    return {
        "name": "mcp_outer_launcher",
        "status": status,
        "path": str(mcp_path),
        "server": "paper-search-mcp",
        "command": command,
        "args": [str(arg) for arg in args],
        "outer_command_available": command_available,
        "launcher_script": str(launcher_script) if launcher_script else None,
        "launcher_script_exists": launcher_script_exists,
        "error": error,
        "message": (
            "plugin .mcp.json outer launcher is available"
            if not error
            else "plugin .mcp.json outer command or launcher script is missing; Codex may fail before runtime.json is loaded"
        ),
    }


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


def _relative_plugin_path(plugin_root: Path, path: Path) -> str:
    try:
        return path.relative_to(plugin_root).as_posix()
    except ValueError:
        return str(path)


def _load_routed_workflows(routing_path: Path) -> tuple[list[str], list[str]]:
    if not routing_path.exists():
        return [], ["skills/routing.yaml is missing"]

    text = routing_path.read_text(encoding="utf-8")
    try:
        import yaml
    except ModuleNotFoundError:
        yaml = None

    if yaml is not None:
        loaded = yaml.safe_load(text) or {}
        routes = loaded.get("routes", {}) if isinstance(loaded, dict) else {}
        workflows = []
        for route in routes.values():
            if not isinstance(route, dict):
                continue
            route_workflows = route.get("workflows", [])
            if isinstance(route_workflows, list):
                workflows.extend(str(workflow) for workflow in route_workflows)
        return sorted(set(workflows)), []

    workflows = []
    in_workflows = False
    for line in text.splitlines():
        if line.startswith("    workflows:"):
            in_workflows = True
            continue
        if in_workflows:
            if line.startswith("      - "):
                workflows.append(line.split("- ", 1)[1].strip())
                continue
            if line.startswith("    ") and not line.startswith("      "):
                in_workflows = False
    return sorted(set(workflows)), []


def _check_skill_bundle_contract(plugin_root: Path) -> dict:
    skills_root = plugin_root / "skills"
    routing_path = skills_root / "routing.yaml"
    skill_paths = sorted(skills_root.glob("*/SKILL.md")) if skills_root.exists() else []
    skill_names = [path.parent.name for path in skill_paths]
    agent_metadata = []
    missing_agent_metadata = []

    for skill_name in skill_names:
        metadata_path = skills_root / skill_name / "agents" / "openai.yaml"
        relative_path = _relative_plugin_path(plugin_root, metadata_path)
        if metadata_path.exists() and metadata_path.is_file() and metadata_path.read_text(encoding="utf-8").strip():
            agent_metadata.append(relative_path)
        else:
            missing_agent_metadata.append(relative_path)

    routed_workflows, issues = _load_routed_workflows(routing_path)
    workflows = []
    missing_workflows = []
    empty_workflows = []
    for workflow in routed_workflows:
        workflow_path = skills_root / workflow
        relative_path = _relative_plugin_path(plugin_root, workflow_path)
        if not workflow_path.exists():
            missing_workflows.append(relative_path)
        elif not workflow_path.read_text(encoding="utf-8").strip():
            empty_workflows.append(relative_path)
        else:
            workflows.append(relative_path)

    actual_workflows = sorted(
        _relative_plugin_path(plugin_root, path)
        for path in skills_root.glob("*/workflows/*.md")
    ) if skills_root.exists() else []
    orphan_workflows = sorted(
        set(actual_workflows) - set(workflows) - set(missing_workflows) - set(empty_workflows)
    )
    missing = missing_agent_metadata + missing_workflows + empty_workflows + orphan_workflows + issues
    status = "error" if missing else "ok"

    return {
        "name": "skill_bundle_contract",
        "status": status,
        "message": (
            f"{len(skill_names)} skills, {len(agent_metadata)} agent metadata files, "
            f"{len(workflows)} routed workflows via skills/routing.yaml"
            if status == "ok"
            else "missing or unrouted skill bundle discovery artifacts"
        ),
        "skill_count": len(skill_names),
        "skills": skill_names,
        "agent_metadata_count": len(agent_metadata),
        "agent_metadata": agent_metadata,
        "missing_agent_metadata": missing_agent_metadata,
        "workflow_count": len(workflows),
        "workflows": workflows,
        "missing_workflows": missing_workflows,
        "empty_workflows": empty_workflows,
        "orphan_workflows": orphan_workflows,
        "routing_path": _relative_plugin_path(plugin_root, routing_path),
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
    runtime_status = apply_runtime_config()
    plugin_metadata, manifest_check = _load_plugin_metadata(plugin_root)
    checks = [manifest_check]
    checks.extend(_check_path(plugin_root, relative_path) for relative_path in REQUIRED_PATHS if relative_path != ".codex-plugin/plugin.json")
    checks.append(_check_skill_bundle_contract(plugin_root))
    checks.append(_check_epi_config(vault_path))
    checks.append(_check_mcp_outer_launcher(plugin_root))
    checks.append(_check_paper_search_mcp_server())
    checks.append(_check_codex_mcp_registration())
    checks.append(_check_paper_search(paper_search_command))
    checks.append(_check_paper_search_provider_readiness())
    checks.append(_check_mineru_command(plugin_root, mineru_command))
    checks.append(_check_mineru_token())
    checks.append(_check_easyscholar())
    overall_status = "error" if any(check["status"] == "error" for check in checks) else "ok"
    report = {
        "overall_status": overall_status,
        "plugin_root": str(plugin_root),
        "plugin": plugin_metadata,
        "default_vault": str(vault_path),
        "runtime_config": runtime_status,
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
