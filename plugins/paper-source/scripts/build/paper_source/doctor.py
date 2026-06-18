from __future__ import annotations

import json
import os
import re
import shutil
import webbrowser
from pathlib import Path

from paper_source.artifacts import read_json
from paper_source.config import config_status
from paper_source.paper_search_adapter import paper_search_provider_readiness
from paper_source.paper_search_adapter import paper_search_source_capabilities
from paper_source.paper_search_adapter import probe_paper_search_mcp
from paper_source.paper_search_adapter import probe_paper_search_mcp_server
from paper_source.run_mineru_parse import _command_tokens
from paper_source.runtime_config import apply_runtime_config


REQUIRED_PATHS = [
    ".codex-plugin/plugin.json",
    "scripts/orchestrator.py",
    "scripts/build/paper_source",
    "build/mineru-paper-parser/mineru_batch_to_md.py",
    "skills/paper-discovery/SKILL.md",
    "skills/paper-ingest/SKILL.md",
    "skills/mineru-paper-parser",
    "templates/interests.example.yaml",
    "templates/routing-rules.example.yaml",
    "templates/wiki/manifest.json",
    "docs",
    "metric-packs/paper-source-quality-gates",
]

PAPER_SEARCH_SETUP_URL = "https://github.com/openags/paper-search-mcp"
MINERU_TOKEN_SETUP_URL = "https://mineru.net/apiManage/docs?openApplyModal=true"
EASYSCHOLAR_SETUP_URL = "https://www.easyscholar.cc"
GROK_SEARCH_RS_SETUP_URL = "https://github.com/"

SETUP_GUIDES = {
    "paper_search_mcp": {
        "summary": "Configure paper-search MCP server",
        "url": PAPER_SEARCH_SETUP_URL,
        "description": "Install the upstream MCP server or point PAPER_SOURCE_PAPER_SEARCH_MCP_COMMAND at a local wrapper.",
        "commands": [
            "python -m paper_search_mcp.server",
            "$env:PAPER_SOURCE_PAPER_SEARCH_MCP_COMMAND='python'",
            "$env:PAPER_SOURCE_PAPER_SEARCH_MCP_ARGS='-m paper_search_mcp.server'",
        ],
    },
    "paper_search_cli": {
        "summary": "Configure paper-search CLI",
        "url": PAPER_SEARCH_SETUP_URL,
        "description": "Install the upstream CLI or point PAPER_SOURCE_PAPER_SEARCH_COMMAND at a local wrapper for fallback.",
        "commands": [
            "uvx --from git+https://github.com/openags/paper-search-mcp.git paper-search --help",
            "$env:PAPER_SOURCE_PAPER_SEARCH_COMMAND='<path-to-paper-search-wrapper>'",
        ],
    },
    "mineru_token": {
        "summary": "Configure MINERU_TOKEN",
        "url": MINERU_TOKEN_SETUP_URL,
        "description": "Create a MinerU API token, then expose it to Paper Source as MINERU_TOKEN.",
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
    "grok_search_mcp": {
        "summary": "Configure optional grok-search-rs MCP",
        "url": GROK_SEARCH_RS_SETUP_URL,
        "description": "Point Paper Source at a local grok-search-rs MCP command and load provider keys via env_file.",
        "commands": [
            "$env:PAPER_SOURCE_GROK_SEARCH_MCP_COMMAND='<path-to-grok-search-rs>'",
            "$env:PAPER_SOURCE_GROK_SEARCH_MCP_ARGS='<stdio args if needed>'",
        ],
    },
}

MCP_SECTION_PATTERN = re.compile(
    r"""^\s*\[\s*mcp_servers\s*\.\s*(?:"([^"]+)"|'([^']+)'|([A-Za-z0-9_-]+))\s*\]\s*$"""
)
MCP_SERVER_REGISTRATIONS = {
    "paper-search-mcp": ("paper_search_mcp_launcher.py", "paper_search_mcp_launcher.cmd"),
    "grok-search-rs": ("grok_search_mcp_launcher.py", "grok_search_mcp_launcher.cmd"),
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
        payload = read_json(manifest_path)
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
    selected_command = command or os.environ.get("PAPER_SOURCE_PAPER_SEARCH_COMMAND") or "paper-search"
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


def _check_grok_search_mcp() -> dict:
    command = os.environ.get("PAPER_SOURCE_GROK_SEARCH_MCP_COMMAND")
    args = os.environ.get("PAPER_SOURCE_GROK_SEARCH_MCP_ARGS")
    if not command:
        return _with_setup(
            {
                "name": "grok_search_mcp",
                "status": "warning",
                "configured": False,
                "message": "optional grok-search-rs MCP is not configured; Grok supplemental search resolves to off",
            }
        )
    executable = command.strip().strip("\"'")
    available = Path(executable).exists() or shutil.which(executable) is not None
    return {
        "name": "grok_search_mcp",
        "status": "ok" if available else "warning",
        "configured": True,
        "command": executable,
        "args_configured": bool(args),
        "message": "optional grok-search-rs MCP command configured"
        if available
        else "optional grok-search-rs MCP command configured but not found on this machine",
    }


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


def _check_runtime_path_policy(runtime_status: dict) -> dict:
    policy = runtime_status.get("path_policy") if isinstance(runtime_status, dict) else {}
    policy = policy if isinstance(policy, dict) else {}
    issues = policy.get("issues") if isinstance(policy.get("issues"), list) else []
    return {
        "name": "runtime_path_policy",
        "status": "warning" if issues else "ok",
        "message": (
            "runtime.json contains paths outside the installed user plugin runtime boundary"
            if issues
            else "runtime paths stay within the installed user plugin runtime boundary or installed executables"
        ),
        "active": policy.get("active"),
        "runtime_root": policy.get("runtime_root"),
        "standard_runtime_root": policy.get("standard_runtime_root"),
        "allowed_env_file_root": policy.get("allowed_env_file_root"),
        "issues": issues,
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
            "shadowed_servers": [],
        }
    try:
        lines = config_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return {
            "name": "codex_mcp_registration",
            "status": "warning",
            "path": str(config_path),
            "message": f"could not read Codex config.toml to check plugin MCP registrations: {exc}",
            "shadowing_static_config": None,
            "shadowed_servers": [],
        }
    shadowed_servers = []
    for line_number, line in enumerate(lines, start=1):
        match = MCP_SECTION_PATTERN.match(line)
        if not match:
            continue
        server_name = next((group for group in match.groups() if group), "")
        if server_name in MCP_SERVER_REGISTRATIONS:
            shadowed_servers.append({"server": server_name, "line": line_number})
    if shadowed_servers:
        first = shadowed_servers[0]
        names = ", ".join(item["server"] for item in shadowed_servers)
        return {
            "name": "codex_mcp_registration",
            "status": "warning",
            "path": str(config_path),
            "line": first["line"],
            "server": first["server"],
            "message": (
                f"user-level mcp_servers entries can shadow Paper Source plugin .mcp.json self-registration "
                f"for: {names}; remove those static blocks unless intentionally overriding the plugin"
            ),
            "shadowing_static_config": True,
            "shadowed_servers": shadowed_servers,
        }
    return {
        "name": "codex_mcp_registration",
        "status": "ok",
        "path": str(config_path),
        "message": "no user-level plugin MCP static registration found",
        "shadowing_static_config": False,
        "shadowed_servers": [],
    }


def _expand_plugin_path(plugin_root: Path, value: str) -> Path:
    expanded = value.replace("${CLAUDE_PLUGIN_ROOT}", str(plugin_root))
    path = Path(expanded).expanduser()
    if not path.is_absolute():
        path = plugin_root / path
    return path


def _looks_like_path(value: str) -> bool:
    return any(separator in value for separator in ("/", "\\")) or bool(Path(value).drive)


def _outer_command_available(plugin_root: Path, command: str) -> bool:
    if not command:
        return False
    if _looks_like_path(command) or "${CLAUDE_PLUGIN_ROOT}" in command:
        return _expand_plugin_path(plugin_root, command).exists()
    return shutil.which(command) is not None


def _launcher_script_from_args(plugin_root: Path, args: list[object], launcher_names: tuple[str, ...]) -> Path | None:
    for arg in args:
        text = str(arg)
        if any(name in text for name in launcher_names):
            return _expand_plugin_path(plugin_root, text)
    return None


def _launcher_arg_from_args(args: list[object], launcher_names: tuple[str, ...]) -> str | None:
    for arg in args:
        text = str(arg)
        if any(name in text for name in launcher_names):
            return text
    return None


def _contains_plugin_root_placeholder(values: list[str]) -> bool:
    return any("${CLAUDE_PLUGIN_ROOT}" in value or "${PLUGIN_ROOT}" in value for value in values)


def _is_relative_path_value(value: str) -> bool:
    return _looks_like_path(value) and not Path(value).expanduser().is_absolute()


def _check_mcp_outer_launcher_server(
    plugin_root: Path,
    mcp_path: Path,
    server_name: str,
    server: object,
    launcher_names: tuple[str, ...],
) -> dict:
    if not isinstance(server, dict):
        return {
            "path": str(mcp_path),
            "server": server_name,
            "status": "warning",
            "error": "registration_missing",
            "message": f"plugin .mcp.json does not register {server_name}",
        }
    command = str(server.get("command") or "")
    cwd = str(server.get("cwd") or "")
    raw_args = server.get("args")
    args = raw_args if isinstance(raw_args, list) else []
    arg_texts = [str(arg) for arg in args]
    cwd_path = _expand_plugin_path(plugin_root, cwd) if cwd else None
    cwd_available = True if not cwd else cwd_path.exists()
    launcher_arg = _launcher_arg_from_args(args, launcher_names)
    launcher_script = _launcher_script_from_args(plugin_root, args, launcher_names)
    launcher_script_exists = bool(launcher_script and launcher_script.exists())
    command_available = _outer_command_available(plugin_root, command)
    error = None
    if _contains_plugin_root_placeholder([command, cwd, *arg_texts]):
        error = "unresolved_plugin_root_placeholder"
    elif not command_available:
        error = "outer_command_not_found"
    elif not cwd_available:
        error = "outer_cwd_not_found"
    elif launcher_arg and _is_relative_path_value(launcher_arg) and not cwd:
        error = "relative_launcher_without_cwd"
    elif not launcher_script_exists:
        error = "launcher_script_not_found"
    status = "warning" if error else "ok"
    return {
        "status": status,
        "path": str(mcp_path),
        "server": server_name,
        "cwd": cwd or None,
        "cwd_path": str(cwd_path) if cwd_path else None,
        "cwd_available": cwd_available,
        "command": command,
        "args": arg_texts,
        "outer_command_available": command_available,
        "launcher_script": str(launcher_script) if launcher_script else None,
        "launcher_script_exists": launcher_script_exists,
        "error": error,
        "message": (
            f"plugin .mcp.json outer launcher for {server_name} is available"
            if not error
            else f"plugin .mcp.json outer launcher config for {server_name} cannot be resolved by Codex before runtime.json is loaded"
        ),
    }


def _check_mcp_outer_launcher(plugin_root: Path) -> dict:
    mcp_path = plugin_root / ".mcp.json"
    if not mcp_path.exists():
        return {
            "name": "mcp_outer_launcher",
            "status": "warning",
            "path": str(mcp_path),
            "server": "paper-search-mcp",
            "error": "plugin_mcp_json_missing",
            "message": "plugin .mcp.json is missing; plugin MCP self-registration will not be installed",
        }
    try:
        payload = read_json(mcp_path)
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
    server_checks = {
        server_name: _check_mcp_outer_launcher_server(
            plugin_root,
            mcp_path,
            server_name,
            servers.get(server_name) if isinstance(servers, dict) else None,
            launcher_names,
        )
        for server_name, launcher_names in MCP_SERVER_REGISTRATIONS.items()
    }
    first_issue = next((check for check in server_checks.values() if check["status"] == "warning"), None)
    primary = first_issue or server_checks["paper-search-mcp"]
    status = "warning" if first_issue else "ok"
    return {
        **primary,
        "name": "mcp_outer_launcher",
        "status": status,
        "servers": server_checks,
        "message": (
            "plugin .mcp.json outer launchers are available"
            if not first_issue
            else primary["message"]
        ),
    }


def _check_paper_source_config(vault_path: Path) -> dict:
    status = config_status(vault_path)
    configured = bool(status["configured"])
    return {
        "name": "paper_source_config",
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
    checks.append(_check_paper_source_config(vault_path))
    checks.append(_check_runtime_path_policy(runtime_status))
    checks.append(_check_mcp_outer_launcher(plugin_root))
    checks.append(_check_paper_search_mcp_server())
    checks.append(_check_codex_mcp_registration())
    checks.append(_check_paper_search(paper_search_command))
    checks.append(_check_paper_search_provider_readiness())
    checks.append(_check_grok_search_mcp())
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
        "Paper Source Doctor",
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
