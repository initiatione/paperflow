import json
import sys
from pathlib import Path

from paper_source.orchestrator import main


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _seed_plugin_root(tmp_path):
    plugin_root = tmp_path / "plugin"
    _write_json(
        plugin_root / ".codex-plugin" / "plugin.json",
        {
            "name": "paper-source",
            "version": "0.1.0-test",
            "description": "Fixture Paper Source plugin",
            "author": {"name": "test"},
            "skills": "./skills/",
            "interface": {
                "displayName": "Paper Source",
                "shortDescription": "Fixture",
                "longDescription": "Fixture",
                "developerName": "test",
                "category": "Productivity",
                "capabilities": ["Read"],
            },
        },
    )
    for path in [
        "scripts/build/paper_source",
        "build/mineru-paper-parser",
        "skills/paper-discovery",
        "skills/paper-discovery/agents",
        "skills/paper-discovery/workflows",
        "skills/paper-ingest",
        "skills/paper-ingest/agents",
        "skills/paper-ingest/workflows",
        "skills/mineru-paper-parser",
        "skills/mineru-paper-parser/agents",
        "templates",
        "templates/wiki",
        "docs",
        "metric-packs/paper-source-quality-gates",
    ]:
        (plugin_root / path).mkdir(parents=True, exist_ok=True)
    (plugin_root / "templates" / "interests.example.yaml").write_text("profile: robotics_ai_control\n", encoding="utf-8")
    (plugin_root / "templates" / "routing-rules.example.yaml").write_text("stages: []\n", encoding="utf-8")
    (plugin_root / "templates" / "wiki" / "manifest.json").write_text("{}\n", encoding="utf-8")
    (plugin_root / "scripts" / "orchestrator.py").write_text("# wrapper\n", encoding="utf-8")
    (plugin_root / "build" / "mineru-paper-parser" / "mineru_batch_to_md.py").write_text("# wrapper\n", encoding="utf-8")
    (plugin_root / "skills" / "paper-discovery" / "SKILL.md").write_text("# Discovery\n", encoding="utf-8")
    (plugin_root / "skills" / "paper-discovery" / "agents" / "openai.yaml").write_text(
        "interface:\n  display_name: Discovery\n  short_description: Find and rank papers\n  default_prompt: $paper-discovery\n",
        encoding="utf-8",
    )
    (plugin_root / "skills" / "paper-discovery" / "workflows" / "run-discovery.md").write_text(
        "# Run discovery\n",
        encoding="utf-8",
    )
    (plugin_root / "skills" / "paper-ingest" / "SKILL.md").write_text("# Ingest\n", encoding="utf-8")
    (plugin_root / "skills" / "paper-ingest" / "agents" / "openai.yaml").write_text(
        "interface:\n  display_name: Ingest\n  short_description: Prepare source bundles\n  default_prompt: $paper-ingest\n",
        encoding="utf-8",
    )
    (plugin_root / "skills" / "paper-ingest" / "workflows" / "prepare-ranked.md").write_text(
        "# Prepare ranked\n",
        encoding="utf-8",
    )
    (plugin_root / "skills" / "mineru-paper-parser" / "SKILL.md").write_text("# MinerU\n", encoding="utf-8")
    (plugin_root / "skills" / "mineru-paper-parser" / "agents" / "openai.yaml").write_text(
        "interface:\n  display_name: MinerU\n  short_description: Parse paper PDFs\n  default_prompt: $mineru-paper-parser\n",
        encoding="utf-8",
    )
    (plugin_root / "skills" / "routing.yaml").write_text(
        "\n".join(
            [
                "routes:",
                "  paper_discovery:",
                "    category: primary",
                "    skill: paper-discovery/SKILL.md",
                "    workflows:",
                "      - paper-discovery/workflows/run-discovery.md",
                "  paper_ingest:",
                "    category: primary",
                "    skill: paper-ingest/SKILL.md",
                "    workflows:",
                "      - paper-ingest/workflows/prepare-ranked.md",
                "  mineru_paper_parser:",
                "    category: support",
                "    skill: mineru-paper-parser/SKILL.md",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return plugin_root


def _write_plugin_mcp(plugin_root, command="python", args=None, cwd="."):
    (plugin_root / "scripts" / "paper_search_mcp_launcher.py").write_text("# launcher\n", encoding="utf-8")
    server = {
        "command": command,
        "args": args or ["./scripts/paper_search_mcp_launcher.py"],
    }
    if cwd is not None:
        server["cwd"] = cwd
    _write_json(
        plugin_root / ".mcp.json",
        {
            "mcpServers": {
                "paper-search-mcp": server
            }
        },
    )


def _run_orchestrator_cli(monkeypatch, capsys, *args, codex_home=None):
    plugin_root = None
    for index, arg in enumerate(args):
        if arg == "--plugin-root" and index + 1 < len(args):
            plugin_root = Path(args[index + 1])
            break
    selected_codex_home = Path(codex_home) if codex_home else (plugin_root.parent if plugin_root else Path.cwd()) / "codex-home"
    monkeypatch.setenv("CODEX_HOME", str(selected_codex_home))
    monkeypatch.setattr(sys, "argv", ["paper_source.orchestrator", *args])
    exit_code = main()
    output = capsys.readouterr().out
    return exit_code, output


def test_doctor_text_reports_ok_with_external_dependency_warnings(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("MINERU_TOKEN", raising=False)
    monkeypatch.delenv("PAPER_SOURCE_PAPER_SEARCH_COMMAND", raising=False)
    monkeypatch.setenv("PAPER_SOURCE_PAPER_SEARCH_MCP_DISABLED", "1")
    plugin_root = _seed_plugin_root(tmp_path)

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "doctor",
        "--plugin-root",
        str(plugin_root),
        "--vault",
        str(tmp_path / "vault"),
        "--paper-search-command",
        "definitely-missing-paper-search-command",
    )

    assert exit_code == 0
    assert "Paper Source Doctor" in output
    assert "overall_status=ok" in output
    assert "plugin_version=0.1.0-test" in output
    assert "default_vault=" in output
    assert "paper_source_config: warning" in output
    assert "init-config" in output
    assert "paper_search_mcp: warning" in output
    assert "paper_search_cli: warning" in output
    assert "mineru_token: warning" in output
    assert "First-use setup:" in output
    assert "paper_search_mcp: Configure paper-search MCP server" in output
    assert "paper_search_cli: Configure paper-search CLI" in output
    assert "mineru_token: Configure MINERU_TOKEN" in output
    assert "doctor --open-setup" in output


def test_doctor_json_reports_structured_checks(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("MINERU_TOKEN", raising=False)
    monkeypatch.delenv("PAPER_SOURCE_PAPER_SEARCH_COMMAND", raising=False)
    monkeypatch.delenv("PAPER_SEARCH_MCP_UNPAYWALL_EMAIL", raising=False)
    monkeypatch.delenv("PAPER_SEARCH_MCP_CORE_API_KEY", raising=False)
    monkeypatch.delenv("PAPER_SEARCH_MCP_GOOGLE_SCHOLAR_PROXY_URL", raising=False)
    monkeypatch.setenv("PAPER_SOURCE_PAPER_SEARCH_MCP_DISABLED", "1")
    plugin_root = _seed_plugin_root(tmp_path)

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "doctor",
        "--plugin-root",
        str(plugin_root),
        "--vault",
        str(tmp_path / "vault"),
        "--paper-search-command",
        "definitely-missing-paper-search-command",
        "--json",
    )

    payload = json.loads(output)

    assert exit_code == 0
    assert payload["overall_status"] == "ok"
    assert payload["plugin"]["name"] == "paper-source"
    assert payload["plugin"]["version"] == "0.1.0-test"
    assert payload["default_vault"] == str((tmp_path / "vault").resolve())
    assert {check["name"]: check["status"] for check in payload["checks"]}["paper_search_mcp"] == "warning"
    assert {check["name"]: check["status"] for check in payload["checks"]}["paper_search_cli"] == "warning"
    config_check = {check["name"]: check for check in payload["checks"]}["paper_source_config"]
    assert config_check["status"] == "warning"
    assert config_check["configured"] is False
    assert config_check["needs_onboarding"] is True
    assert config_check["config_path"] == str((tmp_path / "vault" / "_paper_source" / "meta" / "paper-source-config.yaml").resolve())
    assert "init-config" in config_check["message"]
    assert payload["setup_required"] is True
    setup_by_check = {check["name"]: check.get("setup") for check in payload["checks"]}
    assert setup_by_check["paper_search_mcp"]["summary"] == "Configure paper-search MCP server"
    assert setup_by_check["paper_search_mcp"]["url"] == "https://github.com/openags/paper-search-mcp"
    assert setup_by_check["paper_search_cli"]["summary"] == "Configure paper-search CLI"
    assert setup_by_check["paper_search_cli"]["url"] == "https://github.com/openags/paper-search-mcp"
    assert setup_by_check["mineru_token"]["summary"] == "Configure MINERU_TOKEN"
    assert setup_by_check["mineru_token"]["url"] == "https://mineru.net/apiManage/docs?openApplyModal=true"
    readiness = {check["name"]: check for check in payload["checks"]}["paper_search_provider_readiness"]
    assert readiness["status"] == "warning"
    assert readiness["providers"]["unpaywall"]["status"] == "missing_required_env"
    assert readiness["providers"]["unpaywall"]["env"] == "PAPER_SEARCH_MCP_UNPAYWALL_EMAIL"
    assert readiness["providers"]["core"]["status"] == "missing_recommended_env"
    assert readiness["providers"]["google_scholar"]["status"] == "missing_optional_env"
    assert readiness["capabilities"]["crossref"]["read"] == "info-only"
    assert readiness["capabilities"]["openalex"]["download"] == "unsupported"
    registration = {check["name"]: check for check in payload["checks"]}["codex_mcp_registration"]
    assert registration["status"] == "ok"
    assert registration["shadowing_static_config"] is False


def test_doctor_warns_when_user_config_shadows_plugin_mcp_registration(tmp_path, monkeypatch, capsys):
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text(
        "[mcp_servers.paper-search-mcp]\n"
        'command = "D:/MiniConda/envs/default/python.exe"\n'
        'args = ["-m", "paper_search_mcp.server"]\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    plugin_root = _seed_plugin_root(tmp_path)

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "doctor",
        "--plugin-root",
        str(plugin_root),
        "--vault",
        str(tmp_path / "vault"),
        "--json",
        codex_home=codex_home,
    )

    payload = json.loads(output)
    registration = {check["name"]: check for check in payload["checks"]}["codex_mcp_registration"]

    assert exit_code == 0
    assert registration["status"] == "warning"
    assert registration["shadowing_static_config"] is True
    assert registration["line"] == 1
    assert "shadow" in registration["message"]


def test_doctor_warns_when_plugin_mcp_outer_launcher_command_is_missing(tmp_path, monkeypatch, capsys):
    plugin_root = _seed_plugin_root(tmp_path)
    _write_plugin_mcp(plugin_root, command="missing-python-for-mcp-launcher")

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "doctor",
        "--plugin-root",
        str(plugin_root),
        "--vault",
        str(tmp_path / "vault"),
        "--json",
    )

    payload = json.loads(output)
    outer_launcher = {check["name"]: check for check in payload["checks"]}["mcp_outer_launcher"]

    assert exit_code == 0
    assert outer_launcher["status"] == "warning"
    assert outer_launcher["server"] == "paper-search-mcp"
    assert outer_launcher["command"] == "missing-python-for-mcp-launcher"
    assert outer_launcher["error"] == "outer_command_not_found"
    assert outer_launcher["launcher_script_exists"] is True


def test_doctor_warns_when_plugin_mcp_outer_launcher_uses_unexpanded_plugin_root_placeholder(
    tmp_path, monkeypatch, capsys
):
    plugin_root = _seed_plugin_root(tmp_path)
    _write_plugin_mcp(
        plugin_root,
        args=["${CLAUDE_PLUGIN_ROOT}/scripts/paper_search_mcp_launcher.py"],
        cwd=None,
    )

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "doctor",
        "--plugin-root",
        str(plugin_root),
        "--vault",
        str(tmp_path / "vault"),
        "--json",
    )

    payload = json.loads(output)
    outer_launcher = {check["name"]: check for check in payload["checks"]}["mcp_outer_launcher"]

    assert exit_code == 0
    assert outer_launcher["status"] == "warning"
    assert outer_launcher["error"] == "unresolved_plugin_root_placeholder"
    assert "${CLAUDE_PLUGIN_ROOT}" in outer_launcher["args"][0]


def test_doctor_reports_skill_agent_and_workflow_discovery_contract(tmp_path, monkeypatch, capsys):
    plugin_root = _seed_plugin_root(tmp_path)

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "doctor",
        "--plugin-root",
        str(plugin_root),
        "--vault",
        str(tmp_path / "vault"),
        "--paper-search-command",
        "definitely-missing-paper-search-command",
        "--json",
    )

    payload = json.loads(output)
    checks = {check["name"]: check for check in payload["checks"]}
    skill_contract = checks["skill_bundle_contract"]

    assert exit_code == 0
    assert skill_contract["status"] == "ok"
    assert skill_contract["skill_count"] == 3
    assert skill_contract["agent_metadata_count"] == 3
    assert skill_contract["workflow_count"] == 2
    assert "skills/routing.yaml" in skill_contract["message"]
    assert "skills/paper-discovery/agents/openai.yaml" in skill_contract["agent_metadata"]
    assert "skills/paper-discovery/workflows/run-discovery.md" in skill_contract["workflows"]


def test_doctor_errors_when_skill_agent_metadata_is_missing(tmp_path, monkeypatch, capsys):
    plugin_root = _seed_plugin_root(tmp_path)
    (plugin_root / "skills" / "paper-ingest" / "agents" / "openai.yaml").unlink()

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "doctor",
        "--plugin-root",
        str(plugin_root),
        "--vault",
        str(tmp_path / "vault"),
        "--paper-search-command",
        "definitely-missing-paper-search-command",
        "--json",
    )

    payload = json.loads(output)
    skill_contract = {check["name"]: check for check in payload["checks"]}["skill_bundle_contract"]

    assert exit_code == 1
    assert payload["overall_status"] == "error"
    assert skill_contract["status"] == "error"
    assert skill_contract["missing_agent_metadata"] == ["skills/paper-ingest/agents/openai.yaml"]


def test_doctor_reports_ok_when_paper_source_config_exists(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MINERU_TOKEN", "test-token")
    plugin_root = _seed_plugin_root(tmp_path)
    vault = tmp_path / "vault"
    config_path = vault / "_paper_source" / "meta" / "paper-source-config.yaml"
    state_path = vault / "_paper_source" / "meta" / "paper-source-config-state.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("profile: robotics_ai_control\n", encoding="utf-8")
    _write_json(state_path, {"configured": True})

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "doctor",
        "--plugin-root",
        str(plugin_root),
        "--vault",
        str(vault),
        "--paper-search-command",
        "definitely-missing-paper-search-command",
        "--json",
    )

    payload = json.loads(output)
    config_check = {check["name"]: check for check in payload["checks"]}["paper_source_config"]

    assert exit_code == 0
    assert config_check["status"] == "ok"
    assert config_check["configured"] is True
    assert config_check["needs_onboarding"] is False
    assert config_check["config_path"] == str(config_path.resolve())


def test_doctor_default_does_not_open_setup_pages(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("MINERU_TOKEN", raising=False)
    monkeypatch.delenv("PAPER_SOURCE_PAPER_SEARCH_COMMAND", raising=False)
    plugin_root = _seed_plugin_root(tmp_path)
    opened = []
    monkeypatch.setattr("paper_source.cli.open_setup_links", lambda report: opened.append(report), raising=False)

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "doctor",
        "--plugin-root",
        str(plugin_root),
        "--vault",
        str(tmp_path / "vault"),
        "--paper-search-command",
        "definitely-missing-paper-search-command",
    )

    assert exit_code == 0
    assert "First-use setup:" in output
    assert opened == []


def test_doctor_open_setup_opens_only_missing_dependency_pages(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("MINERU_TOKEN", raising=False)
    monkeypatch.delenv("PAPER_SOURCE_PAPER_SEARCH_COMMAND", raising=False)
    plugin_root = _seed_plugin_root(tmp_path)
    opened_reports = []

    def fake_open_setup_links(report):
        opened_reports.append(report)
        return ["https://github.com/openags/paper-search-mcp", "https://mineru.net/apiManage/docs?openApplyModal=true"]

    monkeypatch.setattr("paper_source.cli.open_setup_links", fake_open_setup_links, raising=False)

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "doctor",
        "--plugin-root",
        str(plugin_root),
        "--vault",
        str(tmp_path / "vault"),
        "--paper-search-command",
        "definitely-missing-paper-search-command",
        "--open-setup",
        "--json",
    )

    payload = json.loads(output)

    assert exit_code == 0
    assert len(opened_reports) == 1
    assert payload["opened_setup_urls"] == [
        "https://github.com/openags/paper-search-mcp",
        "https://mineru.net/apiManage/docs?openApplyModal=true",
    ]


def test_doctor_returns_nonzero_when_plugin_structure_is_missing(tmp_path, monkeypatch, capsys):
    plugin_root = _seed_plugin_root(tmp_path)
    (plugin_root / "templates" / "interests.example.yaml").unlink()

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "doctor",
        "--plugin-root",
        str(plugin_root),
        "--vault",
        str(tmp_path / "vault"),
        "--json",
    )

    payload = json.loads(output)

    assert exit_code == 1
    assert payload["overall_status"] == "error"
    assert {check["name"]: check["status"] for check in payload["checks"]}["templates/interests.example.yaml"] == "error"
