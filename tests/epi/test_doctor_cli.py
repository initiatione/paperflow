import json
import sys

from epi.orchestrator import main


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _seed_plugin_root(tmp_path):
    plugin_root = tmp_path / "plugin"
    _write_json(
        plugin_root / ".codex-plugin" / "plugin.json",
        {
            "name": "epi",
            "version": "0.1.0-test",
            "description": "Fixture EPI plugin",
            "author": {"name": "test"},
            "skills": "./skills/",
            "interface": {
                "displayName": "EPI",
                "shortDescription": "Fixture",
                "longDescription": "Fixture",
                "developerName": "test",
                "category": "Productivity",
                "capabilities": ["Read"],
            },
        },
    )
    for path in [
        "scripts/build/epi",
        "build/mineru-paper-parser",
        "skills/paper-discovery",
        "skills/paper-ingest",
        "skills/mineru-paper-parser",
        "templates",
        "templates/wiki",
        "docs",
        "metric-packs/epi-quality-gates",
    ]:
        (plugin_root / path).mkdir(parents=True, exist_ok=True)
    (plugin_root / "templates" / "interests.example.yaml").write_text("profile: robotics_ai_control\n", encoding="utf-8")
    (plugin_root / "templates" / "routing-rules.example.yaml").write_text("stages: []\n", encoding="utf-8")
    (plugin_root / "templates" / "wiki" / "manifest.json").write_text("{}\n", encoding="utf-8")
    (plugin_root / "scripts" / "orchestrator.py").write_text("# wrapper\n", encoding="utf-8")
    (plugin_root / "build" / "mineru-paper-parser" / "mineru_batch_to_md.py").write_text("# wrapper\n", encoding="utf-8")
    (plugin_root / "skills" / "paper-discovery" / "SKILL.md").write_text("# Discovery\n", encoding="utf-8")
    (plugin_root / "skills" / "paper-ingest" / "SKILL.md").write_text("# Ingest\n", encoding="utf-8")
    return plugin_root


def _run_orchestrator_cli(monkeypatch, capsys, *args):
    monkeypatch.setattr(sys, "argv", ["epi.orchestrator", *args])
    exit_code = main()
    output = capsys.readouterr().out
    return exit_code, output


def test_doctor_text_reports_ok_with_external_dependency_warnings(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("MINERU_TOKEN", raising=False)
    monkeypatch.delenv("EPI_PAPER_SEARCH_COMMAND", raising=False)
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
    assert "EPI Doctor" in output
    assert "overall_status=ok" in output
    assert "plugin_version=0.1.0-test" in output
    assert "default_vault=" in output
    assert "epi_config: warning" in output
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
    monkeypatch.delenv("EPI_PAPER_SEARCH_COMMAND", raising=False)
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
    assert payload["plugin"]["name"] == "epi"
    assert payload["plugin"]["version"] == "0.1.0-test"
    assert payload["default_vault"] == str((tmp_path / "vault").resolve())
    assert {check["name"]: check["status"] for check in payload["checks"]}["paper_search_mcp"] == "warning"
    assert {check["name"]: check["status"] for check in payload["checks"]}["paper_search_cli"] == "warning"
    config_check = {check["name"]: check for check in payload["checks"]}["epi_config"]
    assert config_check["status"] == "warning"
    assert config_check["configured"] is False
    assert config_check["needs_onboarding"] is True
    assert config_check["config_path"] == str((tmp_path / "vault" / "_meta" / "epi-config.yaml").resolve())
    assert "init-config" in config_check["message"]
    assert payload["setup_required"] is True
    setup_by_check = {check["name"]: check.get("setup") for check in payload["checks"]}
    assert setup_by_check["paper_search_mcp"]["summary"] == "Configure paper-search MCP server"
    assert setup_by_check["paper_search_mcp"]["url"] == "https://github.com/openags/paper-search-mcp"
    assert setup_by_check["paper_search_cli"]["summary"] == "Configure paper-search CLI"
    assert setup_by_check["paper_search_cli"]["url"] == "https://github.com/openags/paper-search-mcp"
    assert setup_by_check["mineru_token"]["summary"] == "Configure MINERU_TOKEN"
    assert setup_by_check["mineru_token"]["url"] == "https://mineru.net/apiManage/docs?openApplyModal=true"


def test_doctor_reports_ok_when_epi_config_exists(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MINERU_TOKEN", "test-token")
    plugin_root = _seed_plugin_root(tmp_path)
    vault = tmp_path / "vault"
    config_path = vault / "_meta" / "epi-config.yaml"
    state_path = vault / "_meta" / "epi-config-state.json"
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
    config_check = {check["name"]: check for check in payload["checks"]}["epi_config"]

    assert exit_code == 0
    assert config_check["status"] == "ok"
    assert config_check["configured"] is True
    assert config_check["needs_onboarding"] is False
    assert config_check["config_path"] == str(config_path.resolve())


def test_doctor_default_does_not_open_setup_pages(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("MINERU_TOKEN", raising=False)
    monkeypatch.delenv("EPI_PAPER_SEARCH_COMMAND", raising=False)
    plugin_root = _seed_plugin_root(tmp_path)
    opened = []
    monkeypatch.setattr("epi.cli.open_setup_links", lambda report: opened.append(report), raising=False)

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
    monkeypatch.delenv("EPI_PAPER_SEARCH_COMMAND", raising=False)
    plugin_root = _seed_plugin_root(tmp_path)
    opened_reports = []

    def fake_open_setup_links(report):
        opened_reports.append(report)
        return ["https://github.com/openags/paper-search-mcp", "https://mineru.net/apiManage/docs?openApplyModal=true"]

    monkeypatch.setattr("epi.cli.open_setup_links", fake_open_setup_links, raising=False)

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
