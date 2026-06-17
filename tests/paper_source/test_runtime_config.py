import json
import os
from pathlib import Path

from paper_source.doctor import collect_doctor_report
from paper_source.orchestrator import run_dry_run
from paper_source.runtime_config import apply_runtime_config, runtime_config_path


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


def test_plugin_mcp_registration_uses_runtime_config_launcher():
    plugin_root = Path(__file__).resolve().parents[2] / "plugins" / "paper-source"
    mcp_config = json.loads((plugin_root / ".mcp.json").read_text(encoding="utf-8"))

    server = mcp_config["mcpServers"]["paper-search-mcp"]

    assert server["cwd"] == "."
    assert server["command"] == "cmd"
    assert server["args"] == ["/c", ".\\scripts\\paper_search_mcp_launcher.cmd"]
    assert "${CLAUDE_PLUGIN_ROOT}" not in json.dumps(server)
    assert "paper_search_mcp.server" not in json.dumps(server)
    assert "miniconda" not in json.dumps(server).lower()
    assert "env" not in server
    assert "EPI_PAPER_SEARCH_MCP_LAUNCHER_DEBUG_LOG" not in json.dumps(server)
    assert (plugin_root / "scripts" / "paper_search_mcp_launcher.py").exists()
    assert (plugin_root / "scripts" / "paper_search_mcp_launcher.cmd").exists()


def test_windows_cmd_launcher_uses_current_environment_names_only():
    plugin_root = Path(__file__).resolve().parents[2] / "plugins" / "paper-source"
    cmd_launcher = (plugin_root / "scripts" / "paper_search_mcp_launcher.cmd").read_text(encoding="utf-8")

    assert "import paper_search_mcp" in cmd_launcher
    assert "import sys" not in cmd_launcher
    for current_name in [
        "PAPER_SOURCE_RUNTIME_CONFIG",
        "PAPER_SOURCE_PAPER_SEARCH_MCP_LAUNCHER_PYTHON",
        "PAPER_SOURCE_PAPER_SEARCH_MCP_COMMAND",
        "PAPER_SOURCE_PAPER_SEARCH_MCP_LAUNCHER_DEBUG_LOG",
    ]:
        assert current_name in cmd_launcher
    for old_name in [
        "EPI_RUNTIME_CONFIG",
        "EPI_PAPER_SEARCH_MCP_LAUNCHER_PYTHON",
        "EPI_PAPER_SEARCH_MCP_COMMAND",
        "EPI_PAPER_SEARCH_MCP_LAUNCHER_DEBUG_LOG",
    ]:
        assert old_name not in cmd_launcher


def test_paper_search_mcp_launcher_detects_installed_python_when_configured_python_lacks_package(
    tmp_path, monkeypatch
):
    runtime_path = tmp_path / "runtime.json"
    installed_python = tmp_path / "envs" / "default" / "python.exe"
    _write_json(
        runtime_path,
        {
            "paper_search_mcp": {
                "command": "python",
                "args": ["-m", "paper_search_mcp.server"],
            }
        },
    )
    monkeypatch.setenv("PAPER_SOURCE_RUNTIME_CONFIG", str(runtime_path))
    monkeypatch.delenv("PAPER_SOURCE_PAPER_SEARCH_MCP_COMMAND", raising=False)
    monkeypatch.delenv("PAPER_SOURCE_PAPER_SEARCH_MCP_ARGS", raising=False)

    import paper_source.paper_search_mcp_launcher as launcher

    monkeypatch.setattr(
        launcher,
        "_candidate_python_commands",
        lambda configured_command: [configured_command, str(installed_python)],
        raising=False,
    )
    monkeypatch.setattr(
        launcher,
        "_python_can_import_paper_search_mcp",
        lambda command: command == str(installed_python),
        raising=False,
    )

    command = launcher.build_launch_command()

    assert command == [str(installed_python), "-m", "paper_search_mcp.server"]


def test_paper_search_mcp_launcher_detects_installed_python_when_configured_python_path_lacks_package(
    tmp_path, monkeypatch
):
    runtime_path = tmp_path / "runtime.json"
    configured_python = tmp_path / "envs" / "stale" / "python.exe"
    installed_python = tmp_path / "envs" / "default" / "python.exe"
    _write_json(
        runtime_path,
        {
            "paper_search_mcp": {
                "command": str(configured_python),
                "args": ["-m", "paper_search_mcp.server"],
            }
        },
    )
    monkeypatch.setenv("PAPER_SOURCE_RUNTIME_CONFIG", str(runtime_path))
    monkeypatch.delenv("PAPER_SOURCE_PAPER_SEARCH_MCP_COMMAND", raising=False)
    monkeypatch.delenv("PAPER_SOURCE_PAPER_SEARCH_MCP_ARGS", raising=False)

    import paper_source.paper_search_mcp_launcher as launcher

    monkeypatch.setattr(
        launcher,
        "_candidate_python_commands",
        lambda configured_command: [configured_command, str(installed_python)],
        raising=False,
    )
    monkeypatch.setattr(
        launcher,
        "_python_can_import_paper_search_mcp",
        lambda command: command == str(installed_python),
        raising=False,
    )

    command = launcher.build_launch_command()

    assert command == [str(installed_python), "-m", "paper_search_mcp.server"]


def test_paper_search_mcp_launcher_fails_fast_when_package_is_missing(monkeypatch, capsys):
    monkeypatch.setenv("PAPER_SOURCE_RUNTIME_CONFIG", str(Path("missing-runtime.json")))
    monkeypatch.delenv("PAPER_SOURCE_PAPER_SEARCH_MCP_COMMAND", raising=False)
    monkeypatch.delenv("PAPER_SOURCE_PAPER_SEARCH_MCP_ARGS", raising=False)

    import paper_source.paper_search_mcp_launcher as launcher

    monkeypatch.setattr(launcher, "_candidate_python_commands", lambda configured_command: ["missing-python"], raising=False)
    monkeypatch.setattr(launcher, "_python_can_import_paper_search_mcp", lambda command: False, raising=False)

    exit_code = launcher.main()

    assert exit_code == 1
    stderr = capsys.readouterr().err
    assert "paper_search_mcp" in stderr
    assert "runtime.json" in stderr
    assert "PAPER_SOURCE_PAPER_SEARCH_MCP_COMMAND" in stderr


def test_paper_search_mcp_launcher_uses_runtime_config_command_and_provider_env(tmp_path, monkeypatch):
    runtime_path = tmp_path / "runtime.json"
    paper_search_env = tmp_path / "paper-search.env"
    paper_search_env.write_text("PAPER_SEARCH_MCP_UNPAYWALL_EMAIL=researcher@example.org\n", encoding="utf-8")
    _write_json(
        runtime_path,
        {
            "paper_search_mcp": {
                "command": "runtime-python",
                "args": ["-m", "paper_search_mcp.server"],
                "env_file": str(paper_search_env),
            }
        },
    )
    monkeypatch.setenv("PAPER_SOURCE_RUNTIME_CONFIG", str(runtime_path))
    monkeypatch.setenv("PAPER_SEARCH_MCP_UNPAYWALL_EMAIL", "")
    monkeypatch.delenv("PAPER_SOURCE_PAPER_SEARCH_MCP_COMMAND", raising=False)
    monkeypatch.delenv("PAPER_SOURCE_PAPER_SEARCH_MCP_ARGS", raising=False)

    from paper_source.paper_search_mcp_launcher import build_launch_command

    command = build_launch_command()

    assert command == ["runtime-python", "-m", "paper_search_mcp.server"]
    assert os.environ["PAPER_SEARCH_MCP_UNPAYWALL_EMAIL"] == "researcher@example.org"


def test_apply_runtime_config_loads_plugin_level_commands_and_env_file(tmp_path, monkeypatch):
    runtime_path = tmp_path / "runtime.json"
    mineru_env = tmp_path / "mineru.env"
    mineru_env.write_text(
        "MINERU_TOKEN=dummy-token\n"
        "PAPER_SOURCE_MINERU_COMMAND=from-env-file\n"
        "EASYSCHOLAR_SECRET_KEY=easyscholar-secret\n",
        encoding="utf-8",
    )
    _write_json(
        runtime_path,
        {
            "schema_version": "paper-source-runtime-config-v1",
            "paper_search_mcp": {"command": "runtime-python", "args": ["-m", "paper_search_mcp.server"]},
            "paper_search_cli": {"command": "runtime-paper-search"},
            "mineru": {"env_file": str(mineru_env), "command": "runtime-mineru"},
        },
    )
    monkeypatch.setenv("PAPER_SOURCE_RUNTIME_CONFIG", str(runtime_path))
    for key in [
        "PAPER_SOURCE_PAPER_SEARCH_MCP_COMMAND",
        "PAPER_SOURCE_PAPER_SEARCH_MCP_ARGS",
        "PAPER_SOURCE_PAPER_SEARCH_COMMAND",
        "PAPER_SOURCE_MINERU_COMMAND",
        "MINERU_TOKEN",
        "EASYSCHOLAR_SECRET_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)

    status = apply_runtime_config()

    assert runtime_config_path() == runtime_path
    assert os.environ["PAPER_SOURCE_PAPER_SEARCH_MCP_COMMAND"] == "runtime-python"
    assert os.environ["PAPER_SOURCE_PAPER_SEARCH_MCP_ARGS"] == "-m paper_search_mcp.server"
    assert os.environ["PAPER_SOURCE_PAPER_SEARCH_COMMAND"] == "runtime-paper-search"
    assert os.environ["PAPER_SOURCE_MINERU_COMMAND"] == "runtime-mineru"
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
            "schema_version": "paper-source-runtime-config-v1",
            "easyscholar": {"env_file": str(easyscholar_env)},
        },
    )
    monkeypatch.setenv("PAPER_SOURCE_RUNTIME_CONFIG", str(runtime_path))
    monkeypatch.delenv("EASYSCHOLAR_SECRET_KEY", raising=False)

    status = apply_runtime_config()

    assert os.environ["EASYSCHOLAR_SECRET_KEY"] == "easyscholar-secret"
    assert "EASYSCHOLAR_SECRET_KEY" in status["applied_env"]
    assert status["env_files"][0]["path"] == str(easyscholar_env)
    assert "easyscholar-secret" not in json.dumps(status)


def test_apply_runtime_config_loads_paper_search_provider_env_file(tmp_path, monkeypatch):
    runtime_path = tmp_path / "runtime.json"
    paper_search_env = tmp_path / "paper-search.env"
    paper_search_env.write_text(
        "PAPER_SEARCH_MCP_UNPAYWALL_EMAIL=researcher@example.org\n"
        "PAPER_SEARCH_MCP_SEMANTIC_SCHOLAR_API_KEY=semantic-key\n",
        encoding="utf-8",
    )
    _write_json(
        runtime_path,
        {
            "schema_version": "paper-source-runtime-config-v1",
            "paper_search_mcp": {
                "command": "runtime-python",
                "env_file": str(paper_search_env),
            },
        },
    )
    monkeypatch.setenv("PAPER_SOURCE_RUNTIME_CONFIG", str(runtime_path))
    monkeypatch.delenv("PAPER_SEARCH_MCP_UNPAYWALL_EMAIL", raising=False)
    monkeypatch.delenv("PAPER_SEARCH_MCP_SEMANTIC_SCHOLAR_API_KEY", raising=False)

    status = apply_runtime_config()

    assert os.environ["PAPER_SEARCH_MCP_UNPAYWALL_EMAIL"] == "researcher@example.org"
    assert os.environ["PAPER_SEARCH_MCP_SEMANTIC_SCHOLAR_API_KEY"] == "semantic-key"
    assert "PAPER_SEARCH_MCP_UNPAYWALL_EMAIL" in status["applied_env"]
    assert "PAPER_SEARCH_MCP_SEMANTIC_SCHOLAR_API_KEY" in status["applied_env"]
    assert "researcher@example.org" not in json.dumps(status)
    assert "semantic-key" not in json.dumps(status)


def test_apply_runtime_config_loads_grok_search_mcp_command_and_env_file(tmp_path, monkeypatch):
    runtime_path = tmp_path / "runtime.json"
    grok_env = tmp_path / "grok.env"
    grok_env.write_text(
        "OPENAI_COMPATIBLE_API_URL=https://api.example.org\n"
        "OPENAI_COMPATIBLE_API_KEY=grok-compatible-key\n"
        "OPENAI_COMPATIBLE_MODEL=grok-model\n"
        "GROK_SEARCH_WEB_SEARCH=true\n"
        "GROK_SEARCH_TIMEOUT_SECONDS=120\n"
        "TAVILY_API_KEY=tavily-key\n",
        encoding="utf-8",
    )
    _write_json(
        runtime_path,
        {
            "schema_version": "paper-source-runtime-config-v1",
            "grok_search_mcp": {
                "command": "grok-search-rs",
                "args": ["--stdio"],
                "env_file": str(grok_env),
            },
        },
    )
    monkeypatch.setenv("PAPER_SOURCE_RUNTIME_CONFIG", str(runtime_path))
    for key in [
        "PAPER_SOURCE_GROK_SEARCH_MCP_COMMAND",
        "PAPER_SOURCE_GROK_SEARCH_MCP_ARGS",
        "OPENAI_COMPATIBLE_API_URL",
        "OPENAI_COMPATIBLE_API_KEY",
        "OPENAI_COMPATIBLE_MODEL",
        "GROK_SEARCH_WEB_SEARCH",
        "GROK_SEARCH_TIMEOUT_SECONDS",
        "TAVILY_API_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)

    status = apply_runtime_config()

    assert os.environ["PAPER_SOURCE_GROK_SEARCH_MCP_COMMAND"] == "grok-search-rs"
    assert os.environ["PAPER_SOURCE_GROK_SEARCH_MCP_ARGS"] == "--stdio"
    assert os.environ["OPENAI_COMPATIBLE_API_URL"] == "https://api.example.org"
    assert os.environ["OPENAI_COMPATIBLE_API_KEY"] == "grok-compatible-key"
    assert os.environ["OPENAI_COMPATIBLE_MODEL"] == "grok-model"
    assert os.environ["GROK_SEARCH_WEB_SEARCH"] == "true"
    assert os.environ["GROK_SEARCH_TIMEOUT_SECONDS"] == "120"
    assert os.environ["TAVILY_API_KEY"] == "tavily-key"
    assert "OPENAI_COMPATIBLE_API_URL" in status["applied_env"]
    assert "OPENAI_COMPATIBLE_API_KEY" in status["applied_env"]
    assert "OPENAI_COMPATIBLE_MODEL" in status["applied_env"]
    assert "GROK_SEARCH_WEB_SEARCH" in status["applied_env"]
    assert "GROK_SEARCH_TIMEOUT_SECONDS" in status["applied_env"]
    assert "TAVILY_API_KEY" in status["applied_env"]
    assert "https://api.example.org" not in json.dumps(status)
    assert "grok-compatible-key" not in json.dumps(status)
    assert "grok-model" not in json.dumps(status)
    assert "tavily-key" not in json.dumps(status)


def test_runtime_path_policy_warns_for_standard_runtime_paths_outside_user_plugin_dir(tmp_path, monkeypatch):
    codex_home = tmp_path / "codex-home"
    runtime_root = codex_home / "plugins" / "paperflow" / "paper-source"
    runtime_path = runtime_root / "runtime.json"
    dev_checkout = tmp_path / "paper-search"
    dev_env_dir = dev_checkout / ".env"
    dev_env_dir.mkdir(parents=True)
    (dev_checkout / ".git").mkdir()
    outside_env = dev_env_dir / "paper-search-providers.env"
    outside_env.write_text("PAPER_SEARCH_MCP_UNPAYWALL_EMAIL=researcher@example.org\n", encoding="utf-8")
    helper_script = dev_env_dir / "paper-search-live.ps1"
    helper_script.write_text("paper-search @args\n", encoding="utf-8")
    _write_json(
        runtime_path,
        {
            "schema_version": "paper-source-runtime-config-v1",
            "paper_search_mcp": {"env_file": str(outside_env)},
            "paper_search_cli": {"command": str(helper_script)},
        },
    )
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("PAPER_SOURCE_RUNTIME_CONFIG", str(runtime_path))
    monkeypatch.delenv("PAPER_SEARCH_MCP_UNPAYWALL_EMAIL", raising=False)
    monkeypatch.delenv("PAPER_SOURCE_PAPER_SEARCH_COMMAND", raising=False)

    status = apply_runtime_config()

    policy = status["path_policy"]
    codes = {issue["code"] for issue in policy["issues"]}
    assert policy["active"] is True
    assert "runtime_env_file_outside_user_plugin_runtime" in codes
    assert "runtime_env_file_points_to_development_checkout" in codes
    assert "runtime_command_points_to_env_helper" in codes
    assert "runtime_command_points_to_development_checkout" in codes
    assert any("paper_search_mcp.env_file" in warning for warning in status["warnings"])
    assert any("paper_search_cli.command" in warning for warning in status["warnings"])


def test_runtime_path_policy_allows_custom_test_runtime_env_files(tmp_path, monkeypatch):
    runtime_path = tmp_path / "runtime.json"
    env_file = tmp_path / "paper-search-providers.env"
    env_file.write_text("PAPER_SEARCH_MCP_UNPAYWALL_EMAIL=researcher@example.org\n", encoding="utf-8")
    _write_json(runtime_path, {"paper_search_mcp": {"env_file": str(env_file)}})
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex-home"))
    monkeypatch.setenv("PAPER_SOURCE_RUNTIME_CONFIG", str(runtime_path))
    monkeypatch.delenv("PAPER_SEARCH_MCP_UNPAYWALL_EMAIL", raising=False)

    status = apply_runtime_config()

    assert status["path_policy"]["active"] is False
    assert status["path_policy"]["issues"] == []
    assert os.environ["PAPER_SEARCH_MCP_UNPAYWALL_EMAIL"] == "researcher@example.org"


def test_apply_runtime_config_rejects_grok_provider_secret_in_runtime_env(tmp_path, monkeypatch):
    runtime_path = tmp_path / "runtime.json"
    _write_json(runtime_path, {"env": {"OPENAI_COMPATIBLE_API_KEY": "do-not-load"}})
    monkeypatch.setenv("PAPER_SOURCE_RUNTIME_CONFIG", str(runtime_path))
    monkeypatch.delenv("OPENAI_COMPATIBLE_API_KEY", raising=False)

    status = apply_runtime_config()

    assert "OPENAI_COMPATIBLE_API_KEY" not in os.environ
    assert "OPENAI_COMPATIBLE_API_KEY" in status["skipped_env"]
    assert "do-not-load" not in json.dumps(status)


def test_apply_runtime_config_loads_all_documented_paper_search_provider_env_keys(tmp_path, monkeypatch):
    runtime_path = tmp_path / "runtime.json"
    paper_search_env = tmp_path / "paper-search.env"
    paper_search_env.write_text(
        "\n".join(
            [
                "PAPER_SEARCH_MCP_UNPAYWALL_EMAIL=researcher@example.org",
                "PAPER_SEARCH_MCP_CORE_API_KEY=core-key",
                "PAPER_SEARCH_MCP_SEMANTIC_SCHOLAR_API_KEY=semantic-key",
                "PAPER_SEARCH_MCP_GOOGLE_SCHOLAR_PROXY_URL=https://proxy.example.org",
                "PAPER_SEARCH_MCP_DOAJ_API_KEY=doaj-key",
                "PAPER_SEARCH_MCP_ZENODO_ACCESS_TOKEN=zenodo-token",
                "",
            ]
        ),
        encoding="utf-8",
    )
    _write_json(runtime_path, {"paper_search_mcp": {"env_file": str(paper_search_env)}})
    monkeypatch.setenv("PAPER_SOURCE_RUNTIME_CONFIG", str(runtime_path))
    for key in [
        "PAPER_SEARCH_MCP_UNPAYWALL_EMAIL",
        "PAPER_SEARCH_MCP_CORE_API_KEY",
        "PAPER_SEARCH_MCP_SEMANTIC_SCHOLAR_API_KEY",
        "PAPER_SEARCH_MCP_GOOGLE_SCHOLAR_PROXY_URL",
        "PAPER_SEARCH_MCP_DOAJ_API_KEY",
        "PAPER_SEARCH_MCP_ZENODO_ACCESS_TOKEN",
    ]:
        monkeypatch.delenv(key, raising=False)

    status = apply_runtime_config()

    assert os.environ["PAPER_SEARCH_MCP_GOOGLE_SCHOLAR_PROXY_URL"] == "https://proxy.example.org"
    assert os.environ["PAPER_SEARCH_MCP_ZENODO_ACCESS_TOKEN"] == "zenodo-token"
    assert "PAPER_SEARCH_MCP_GOOGLE_SCHOLAR_PROXY_URL" in status["applied_env"]
    assert "PAPER_SEARCH_MCP_ZENODO_ACCESS_TOKEN" in status["applied_env"]
    assert "https://proxy.example.org" not in json.dumps(status)
    assert "zenodo-token" not in json.dumps(status)


def test_apply_runtime_config_does_not_override_explicit_environment(tmp_path, monkeypatch):
    runtime_path = tmp_path / "runtime.json"
    _write_json(
        runtime_path,
        {
            "paper_search_cli": {"command": "runtime-paper-search"},
            "env": {"PAPER_SOURCE_PAPER_SEARCH_MCP_DISABLED": "1"},
        },
    )
    monkeypatch.setenv("PAPER_SOURCE_RUNTIME_CONFIG", str(runtime_path))
    monkeypatch.setenv("PAPER_SOURCE_PAPER_SEARCH_COMMAND", "explicit-paper-search")

    status = apply_runtime_config()

    assert os.environ["PAPER_SOURCE_PAPER_SEARCH_COMMAND"] == "explicit-paper-search"
    assert os.environ["PAPER_SOURCE_PAPER_SEARCH_MCP_DISABLED"] == "1"
    assert "PAPER_SOURCE_PAPER_SEARCH_COMMAND" in status["skipped_env"]


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
    monkeypatch.setenv("PAPER_SOURCE_RUNTIME_CONFIG", str(runtime_path))
    for key in [
        "PAPER_SOURCE_PAPER_SEARCH_MCP_COMMAND",
        "PAPER_SOURCE_PAPER_SEARCH_MCP_ARGS",
        "PAPER_SOURCE_PAPER_SEARCH_COMMAND",
        "MINERU_TOKEN",
        "EASYSCHOLAR_SECRET_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)

    def fake_mcp_server_probe(timeout_seconds):
        return {
            "available": True,
            "command": os.environ["PAPER_SOURCE_PAPER_SEARCH_MCP_COMMAND"],
            "args": os.environ["PAPER_SOURCE_PAPER_SEARCH_MCP_ARGS"].split(),
        }

    def fake_cli_probe(command):
        return {"available": True, "command": command, "stdout": "paper-search 0.1.4"}

    monkeypatch.setattr("paper_source.doctor.probe_paper_search_mcp_server", fake_mcp_server_probe)
    monkeypatch.setattr("paper_source.doctor.probe_paper_search_mcp", fake_cli_probe)

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


def test_doctor_reports_runtime_path_policy_check(tmp_path, monkeypatch):
    codex_home = tmp_path / "codex-home"
    runtime_root = codex_home / "plugins" / "paperflow" / "paper-source"
    runtime_path = runtime_root / "runtime.json"
    dev_checkout = tmp_path / "paper-search"
    dev_env_dir = dev_checkout / ".env"
    dev_env_dir.mkdir(parents=True)
    (dev_checkout / ".git").mkdir()
    provider_env = dev_env_dir / "paper-search-providers.env"
    provider_env.write_text("PAPER_SEARCH_MCP_UNPAYWALL_EMAIL=researcher@example.org\n", encoding="utf-8")
    _write_json(runtime_path, {"paper_search_mcp": {"env_file": str(provider_env)}})
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("PAPER_SOURCE_RUNTIME_CONFIG", str(runtime_path))
    monkeypatch.setattr("paper_source.doctor.probe_paper_search_mcp_server", lambda timeout_seconds: {"available": False})
    monkeypatch.setattr("paper_source.doctor.probe_paper_search_mcp", lambda command: {"available": False})

    report = collect_doctor_report(
        plugin_root=tmp_path / "plugin",
        vault_path=tmp_path / "vault",
        paper_search_command=None,
    )

    checks = {check["name"]: check for check in report["checks"]}
    assert checks["runtime_path_policy"]["status"] == "warning"
    assert checks["runtime_path_policy"]["active"] is True
    assert checks["runtime_path_policy"]["issues"][0]["code"] == "runtime_env_file_outside_user_plugin_runtime"


def test_doctor_warns_when_easyscholar_secret_is_missing(tmp_path, monkeypatch):
    monkeypatch.delenv("EASYSCHOLAR_SECRET_KEY", raising=False)
    monkeypatch.setattr("paper_source.doctor.probe_paper_search_mcp_server", lambda timeout_seconds: {"available": False})
    monkeypatch.setattr("paper_source.doctor.probe_paper_search_mcp", lambda command: {"available": False})

    report = collect_doctor_report(
        plugin_root=tmp_path / "plugin",
        vault_path=tmp_path / "vault",
        paper_search_command=None,
    )

    checks = {check["name"]: check for check in report["checks"]}
    assert checks["easyscholar"]["status"] == "warning"
    assert checks["easyscholar"]["secret_key"] == "missing"


def test_config_status_include_runtime_reports_easyscholar_secret_without_value(tmp_path, monkeypatch, capsys):
    from paper_source import cli

    monkeypatch.setenv("EASYSCHOLAR_SECRET_KEY", "easyscholar-secret")
    vault = tmp_path / "vault"
    meta = vault / "_paper_source" / "meta"
    meta.mkdir(parents=True)
    (meta / "paper-source-config.yaml").write_text("profile: general_academic_research\n", encoding="utf-8")

    exit_code = cli.main(["config-status", "--vault", str(vault), "--include-runtime", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["easyscholar_secret_key"] == "set"
    assert "easyscholar-secret" not in json.dumps(payload)


def test_cli_main_applies_runtime_config_before_default_vault_resolution(tmp_path, monkeypatch, capsys):
    from paper_source import cli

    runtime_path = tmp_path / "runtime.json"
    vault = tmp_path / "paper-research-wiki"
    meta = vault / "_paper_source" / "meta"
    meta.mkdir(parents=True)
    (meta / "paper-source-config.yaml").write_text("profile: runtime_vault\n", encoding="utf-8")
    _write_json(runtime_path, {"env": {"PAPER_SOURCE_VAULT": str(vault)}})
    monkeypatch.setenv("PAPER_SOURCE_RUNTIME_CONFIG", str(runtime_path))
    monkeypatch.delenv("PAPER_SOURCE_VAULT", raising=False)

    exit_code = cli.main(["config-status", "--json", "--include-runtime"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["config_path"] == str(vault / "_paper_source" / "meta" / "paper-source-config.yaml")
    assert payload["runtime_config"]["loaded"] is True
    env_mentions = set(payload["runtime_config"]["applied_env"]) | set(payload["runtime_config"]["skipped_env"])
    assert "PAPER_SOURCE_VAULT" in env_mentions


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
            "env": {"PAPER_SOURCE_PAPER_SEARCH_MCP_DISABLED": "1"},
        },
    )
    monkeypatch.setenv("PAPER_SOURCE_RUNTIME_CONFIG", str(runtime_path))
    monkeypatch.delenv("PAPER_SOURCE_PAPER_SEARCH_COMMAND", raising=False)

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
