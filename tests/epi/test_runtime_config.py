import json
import os
from pathlib import Path

from epi.doctor import collect_doctor_report
from epi.orchestrator import run_dry_run
from epi.runtime_config import apply_runtime_config, runtime_config_path


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_minimal_plugin_template(plugin_root: Path) -> None:
    templates = plugin_root / "templates"
    templates.mkdir(parents=True)
    (templates / "interests.example.yaml").write_text(
        "profile: robotics_ai_control\n"
        "domains:\n"
        "  - robotics\n"
        "budget:\n"
        "  max_results: 5\n",
        encoding="utf-8",
    )


def _write_fake_paper_search(tmp_path: Path, payload: dict) -> str:
    script = tmp_path / "runtime-paper-search.ps1"
    script.write_text(
        "if ($args -contains '--version') { Write-Output 'paper-search 0.1.4'; exit 0 }\n"
        f"$payload = @'\n{json.dumps(payload)}\n'@\n"
        "$payload | Write-Output\n"
        "exit 0\n",
        encoding="utf-8",
    )
    return str(script)


def test_apply_runtime_config_loads_plugin_level_commands_and_env_file(tmp_path, monkeypatch):
    runtime_path = tmp_path / "runtime.json"
    mineru_env = tmp_path / "mineru.env"
    mineru_env.write_text(
        "MINERU_TOKEN=dummy-token\n"
        "EPI_MINERU_COMMAND=from-env-file\n"
        "EASYSCHOLAR_SECRET_KEY=easyscholar-secret\n",
        encoding="utf-8",
    )
    _write_json(
        runtime_path,
        {
            "schema_version": "epi-runtime-config-v1",
            "paper_search_mcp": {"command": "runtime-python", "args": ["-m", "paper_search_mcp.server"]},
            "paper_search_cli": {"command": "runtime-paper-search"},
            "mineru": {"env_file": str(mineru_env), "command": "runtime-mineru"},
        },
    )
    monkeypatch.setenv("EPI_RUNTIME_CONFIG", str(runtime_path))
    for key in [
        "EPI_PAPER_SEARCH_MCP_COMMAND",
        "EPI_PAPER_SEARCH_MCP_ARGS",
        "EPI_PAPER_SEARCH_COMMAND",
        "EPI_MINERU_COMMAND",
        "MINERU_TOKEN",
        "EASYSCHOLAR_SECRET_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)

    status = apply_runtime_config()

    assert runtime_config_path() == runtime_path
    assert os.environ["EPI_PAPER_SEARCH_MCP_COMMAND"] == "runtime-python"
    assert os.environ["EPI_PAPER_SEARCH_MCP_ARGS"] == "-m paper_search_mcp.server"
    assert os.environ["EPI_PAPER_SEARCH_COMMAND"] == "runtime-paper-search"
    assert os.environ["EPI_MINERU_COMMAND"] == "runtime-mineru"
    assert os.environ["MINERU_TOKEN"] == "dummy-token"
    assert os.environ["EASYSCHOLAR_SECRET_KEY"] == "easyscholar-secret"
    assert status["loaded"] is True
    assert "MINERU_TOKEN" in status["applied_env"]
    assert "EASYSCHOLAR_SECRET_KEY" in status["applied_env"]
    assert "dummy-token" not in json.dumps(status)
    assert "easyscholar-secret" not in json.dumps(status)


def test_apply_runtime_config_loads_dedicated_easyscholar_env_file(tmp_path, monkeypatch):
    runtime_path = tmp_path / "runtime.json"
    easyscholar_env = tmp_path / "easyscholar.env"
    easyscholar_env.write_text("EASYSCHOLAR_SECRET_KEY=easyscholar-secret\n", encoding="utf-8")
    _write_json(
        runtime_path,
        {
            "schema_version": "epi-runtime-config-v1",
            "easyscholar": {"env_file": str(easyscholar_env)},
        },
    )
    monkeypatch.setenv("EPI_RUNTIME_CONFIG", str(runtime_path))
    monkeypatch.delenv("EASYSCHOLAR_SECRET_KEY", raising=False)

    status = apply_runtime_config()

    assert os.environ["EASYSCHOLAR_SECRET_KEY"] == "easyscholar-secret"
    assert "EASYSCHOLAR_SECRET_KEY" in status["applied_env"]
    assert status["env_files"][0]["path"] == str(easyscholar_env)
    assert "easyscholar-secret" not in json.dumps(status)


def test_apply_runtime_config_does_not_override_explicit_environment(tmp_path, monkeypatch):
    runtime_path = tmp_path / "runtime.json"
    _write_json(
        runtime_path,
        {
            "paper_search_cli": {"command": "runtime-paper-search"},
            "env": {"EPI_PAPER_SEARCH_MCP_DISABLED": "1"},
        },
    )
    monkeypatch.setenv("EPI_RUNTIME_CONFIG", str(runtime_path))
    monkeypatch.setenv("EPI_PAPER_SEARCH_COMMAND", "explicit-paper-search")

    status = apply_runtime_config()

    assert os.environ["EPI_PAPER_SEARCH_COMMAND"] == "explicit-paper-search"
    assert os.environ["EPI_PAPER_SEARCH_MCP_DISABLED"] == "1"
    assert "EPI_PAPER_SEARCH_COMMAND" in status["skipped_env"]


def test_doctor_applies_runtime_config_before_dependency_checks(tmp_path, monkeypatch):
    runtime_path = tmp_path / "runtime.json"
    mineru_env = tmp_path / "mineru.env"
    mineru_env.write_text("MINERU_TOKEN=dummy-token\nEASYSCHOLAR_SECRET_KEY=easyscholar-secret\n", encoding="utf-8")
    _write_json(
        runtime_path,
        {
            "paper_search_mcp": {"command": "runtime-python", "args": "-m paper_search_mcp.server"},
            "paper_search_cli": {"command": "runtime-paper-search"},
            "mineru": {"env_file": str(mineru_env)},
        },
    )
    monkeypatch.setenv("EPI_RUNTIME_CONFIG", str(runtime_path))
    for key in [
        "EPI_PAPER_SEARCH_MCP_COMMAND",
        "EPI_PAPER_SEARCH_MCP_ARGS",
        "EPI_PAPER_SEARCH_COMMAND",
        "MINERU_TOKEN",
        "EASYSCHOLAR_SECRET_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)

    def fake_mcp_server_probe(timeout_seconds):
        return {
            "available": True,
            "command": os.environ["EPI_PAPER_SEARCH_MCP_COMMAND"],
            "args": os.environ["EPI_PAPER_SEARCH_MCP_ARGS"].split(),
        }

    def fake_cli_probe(command):
        return {"available": True, "command": command, "stdout": "paper-search 0.1.4"}

    monkeypatch.setattr("epi.doctor.probe_paper_search_mcp_server", fake_mcp_server_probe)
    monkeypatch.setattr("epi.doctor.probe_paper_search_mcp", fake_cli_probe)

    report = collect_doctor_report(
        plugin_root=tmp_path / "plugin",
        vault_path=tmp_path / "vault",
        paper_search_command=None,
    )

    checks = {check["name"]: check for check in report["checks"]}
    assert checks["paper_search_mcp"]["status"] == "ok"
    assert checks["paper_search_cli"]["status"] == "ok"
    assert checks["mineru_token"]["status"] == "ok"
    assert checks["easyscholar"]["status"] == "ok"
    assert checks["easyscholar"]["secret_key"] == "set"
    assert checks["paper_search_cli"]["command"] == "runtime-paper-search"
    assert report["runtime_config"]["loaded"] is True
    assert "dummy-token" not in json.dumps(report)
    assert "easyscholar-secret" not in json.dumps(report)


def test_doctor_warns_when_easyscholar_secret_is_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("EASYSCHOLAR_SECRET_KEY", raising=False)
    monkeypatch.setattr("epi.doctor.probe_paper_search_mcp_server", lambda timeout_seconds: {"available": False})
    monkeypatch.setattr("epi.doctor.probe_paper_search_mcp", lambda command: {"available": False})

    report = collect_doctor_report(
        plugin_root=tmp_path / "plugin",
        vault_path=tmp_path / "vault",
        paper_search_command=None,
    )

    checks = {check["name"]: check for check in report["checks"]}
    assert checks["easyscholar"]["status"] == "warning"
    assert checks["easyscholar"]["secret_key"] == "missing"


def test_config_status_include_runtime_reports_easyscholar_secret_without_value(tmp_path, monkeypatch, capsys):
    from epi import cli

    monkeypatch.setenv("EASYSCHOLAR_SECRET_KEY", "easyscholar-secret")
    vault = tmp_path / "vault"
    meta = vault / "_epi" / "meta"
    meta.mkdir(parents=True)
    (meta / "epi-config.yaml").write_text("profile: general_academic_research\n", encoding="utf-8")

    exit_code = cli.main(["config-status", "--vault", str(vault), "--include-runtime", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["easyscholar_secret_key"] == "set"
    assert "easyscholar-secret" not in json.dumps(payload)


def test_dry_run_uses_runtime_configured_cli_fallback(tmp_path, monkeypatch):
    plugin_root = tmp_path / "plugin"
    _write_minimal_plugin_template(plugin_root)
    fake_command = _write_fake_paper_search(
        tmp_path,
        {
            "query": "robotics survey",
            "sources_used": ["arxiv"],
            "source_results": {"arxiv": 1},
            "errors": {},
            "total": 1,
            "papers": [
                {
                    "paper_id": "2401.12345",
                    "title": "Robot Control Survey",
                    "authors": "A. Researcher",
                    "abstract": "Robotics control survey with benchmark evidence.",
                    "published_date": "2025-01-02T00:00:00",
                    "pdf_url": "https://arxiv.org/pdf/2401.12345",
                    "url": "https://arxiv.org/abs/2401.12345",
                    "source": "arxiv",
                    "citations": 3,
                    "extra": {},
                }
            ],
        },
    )
    runtime_path = tmp_path / "runtime.json"
    _write_json(
        runtime_path,
        {
            "paper_search_cli": {"command": fake_command},
            "env": {"EPI_PAPER_SEARCH_MCP_DISABLED": "1"},
        },
    )
    monkeypatch.setenv("EPI_RUNTIME_CONFIG", str(runtime_path))
    monkeypatch.delenv("EPI_PAPER_SEARCH_COMMAND", raising=False)

    run_dir = run_dry_run(
        plugin_root=plugin_root,
        vault_path=tmp_path / "vault",
        query="robotics survey",
        max_results=None,
        paper_search_command=None,
        sources=["arxiv"],
        use_query_plan=False,
    )

    search_record = json.loads((run_dir / "search-record.json").read_text(encoding="utf-8"))
    assert search_record["source_mode"] == "paper_search_cli"
    assert search_record["upstream"]["cli_command"].endswith("runtime-paper-search.ps1")
