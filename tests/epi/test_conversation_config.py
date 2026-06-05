import json
import sys

from epi.config import load_config
from epi.orchestrator import main


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _run_orchestrator_cli(monkeypatch, capsys, *args):
    monkeypatch.setattr(sys, "argv", ["epi.orchestrator", *args])
    exit_code = main()
    output = capsys.readouterr().out
    return exit_code, output


def _answers(**overrides):
    payload = {
        "profile": "robotics_ai_control",
        "domains": ["robotics", "embodied intelligence", "control"],
        "positive_keywords": ["humanoid", "model predictive control"],
        "negative_keywords": ["unrelated biomedical trial"],
        "max_results": 17,
        "paper_search_command": "paper-search",
        "paper_search_sources": ["arxiv", "semantic", "openalex"],
        "mineru_token_source": "MINERU_TOKEN env",
        "mineru_command": "python scripts/mineru_batch_to_md.py",
        "zotero_enabled": False,
        "zotero_collection": "EPI",
        "human_gate_mode": "before_promote",
        "configured_by": "tester",
    }
    payload.update(overrides)
    return payload


def test_config_status_reports_missing_config(tmp_path, monkeypatch, capsys):
    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "config-status",
        "--vault",
        str(tmp_path / "vault"),
        "--json",
    )

    payload = json.loads(output)

    assert exit_code == 1
    assert payload["configured"] is False
    assert payload["needs_onboarding"] is True
    assert payload["config_path"].replace("\\", "/").endswith("_epi/meta/epi-config.yaml")


def test_config_status_can_include_values_and_fast_runtime_status(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    answers_path = tmp_path / "answers.json"
    runtime_path = tmp_path / "runtime.json"
    _write_json(answers_path, _answers(profile="robotics_ai_control_research"))
    _write_json(
        runtime_path,
        {
            "schema_version": "epi-runtime-config-v1",
            "paper_search_mcp": {"command": "python", "args": ["-m", "paper_search_mcp.server"]},
            "paper_search_cli": {"command": "paper-search"},
            "mineru": {"env_file": str(tmp_path / "missing-mineru.env")},
        },
    )
    monkeypatch.setenv("EPI_RUNTIME_CONFIG", str(runtime_path))
    monkeypatch.delenv("MINERU_TOKEN", raising=False)
    _run_orchestrator_cli(monkeypatch, capsys, "init-config", "--vault", str(vault), "--answers-json", str(answers_path))

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "config-status",
        "--vault",
        str(vault),
        "--json",
        "--include-values",
        "--include-runtime",
    )
    payload = json.loads(output)

    assert exit_code == 0
    assert payload["config"]["profile"] == "robotics_ai_control_research"
    assert payload["runtime_config"]["path"] == str(runtime_path)
    assert payload["mineru_token"] == "missing"
    assert "secret-token" not in output


def test_init_config_writes_wiki_config_state_and_history(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    answers_path = tmp_path / "answers.json"
    _write_json(answers_path, _answers())

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "init-config",
        "--vault",
        str(vault),
        "--answers-json",
        str(answers_path),
    )

    config_path = vault / "_epi/meta" / "epi-config.yaml"
    state_path = vault / "_epi/meta" / "epi-config-state.json"
    history_files = list((vault / "_epi/meta" / "config-history").glob("*.yaml"))
    state = json.loads(state_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert f"config_path={config_path.resolve()}" in output
    assert config_path.is_file()
    assert "profile: robotics_ai_control" in config_path.read_text(encoding="utf-8")
    assert "max_results: 17" in config_path.read_text(encoding="utf-8")
    assert state["configured"] is True
    assert state["last_action"] == "init-config"
    assert state["configured_by"] == "tester"
    assert len(history_files) == 1


def test_load_config_prefers_wiki_config_over_plugin_template(tmp_path, monkeypatch, capsys):
    plugin_root = tmp_path / "plugin"
    templates = plugin_root / "templates"
    templates.mkdir(parents=True)
    (templates / "interests.example.yaml").write_text(
        "profile: template_profile\n"
        "domains:\n"
        "  - template-domain\n"
        "budget:\n"
        "  max_results: 3\n",
        encoding="utf-8",
    )
    answers_path = tmp_path / "answers.json"
    _write_json(answers_path, _answers(profile="wiki_profile", domains=["robotics", "control"], max_results=23))
    _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "init-config",
        "--vault",
        str(tmp_path / "vault"),
        "--answers-json",
        str(answers_path),
    )

    config = load_config(plugin_root=plugin_root, vault_path=tmp_path / "vault", max_results=None)

    assert config.profile == "wiki_profile"
    assert config.domains == ["robotics", "control"]
    assert config.max_results == 23


def test_propose_config_update_does_not_write_until_apply(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    answers_path = tmp_path / "answers.json"
    proposal_path = tmp_path / "proposal.json"
    _write_json(answers_path, _answers(max_results=11))
    _write_json(
        proposal_path,
        {
            "reason": "raise search budget",
            "changes": {
                "max_results": 29,
                "zotero_enabled": True,
            },
        },
    )
    _run_orchestrator_cli(monkeypatch, capsys, "init-config", "--vault", str(vault), "--answers-json", str(answers_path))
    before = (vault / "_epi/meta" / "epi-config.yaml").read_text(encoding="utf-8")

    propose_exit, propose_output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "propose-config-update",
        "--vault",
        str(vault),
        "--proposal-json",
        str(proposal_path),
        "--json",
    )
    after_propose = (vault / "_epi/meta" / "epi-config.yaml").read_text(encoding="utf-8")

    assert propose_exit == 0
    assert after_propose == before
    proposal = json.loads(propose_output)
    assert proposal["status"] == "proposal"
    assert "budget.max_results: 11 -> 29" in proposal["diff"]
    assert "zotero.enabled: False -> True" in proposal["diff"]

    apply_exit, apply_output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "apply-config-update",
        "--vault",
        str(vault),
        "--proposal-json",
        str(proposal_path),
        "--confirmed-by",
        "tester",
    )
    config_text = (vault / "_epi/meta" / "epi-config.yaml").read_text(encoding="utf-8")
    history_files = list((vault / "_epi/meta" / "config-history").glob("*.yaml"))

    assert apply_exit == 0
    assert "config_updated=true" in apply_output
    assert "max_results: 29" in config_text
    assert "enabled: true" in config_text
    assert len(history_files) == 2


def test_reset_update_preserves_existing_wiki_artifacts(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    for relative in [
        "_epi/raw/keep/paper.pdf",
        "_epi/runs/keep-run/run-state.json",
        "_epi/staging/papers/keep/promotion-plan.json",
        "references/keep.md",
    ]:
        path = vault / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("keep", encoding="utf-8")
    answers_path = tmp_path / "answers.json"
    proposal_path = tmp_path / "proposal.json"
    _write_json(answers_path, _answers(profile="first_profile"))
    _write_json(
        proposal_path,
        {
            "mode": "reset",
            "reason": "rerun onboarding",
            "config": _answers(profile="reset_profile", max_results=31),
        },
    )
    _run_orchestrator_cli(monkeypatch, capsys, "init-config", "--vault", str(vault), "--answers-json", str(answers_path))

    exit_code, _ = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "apply-config-update",
        "--vault",
        str(vault),
        "--proposal-json",
        str(proposal_path),
        "--confirmed-by",
        "tester",
    )

    assert exit_code == 0
    assert "profile: reset_profile" in (vault / "_epi/meta" / "epi-config.yaml").read_text(encoding="utf-8")
    assert (vault / "_epi/raw/keep/paper.pdf").read_text(encoding="utf-8") == "keep"
    assert (vault / "_epi/runs/keep-run/run-state.json").read_text(encoding="utf-8") == "keep"
    assert (vault / "_epi/staging/papers/keep/promotion-plan.json").read_text(encoding="utf-8") == "keep"
    assert (vault / "references/keep.md").read_text(encoding="utf-8") == "keep"


def test_wiki_reset_preserves_config_by_default_and_backs_up_content(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    backup_root = tmp_path / "reset-backup"
    answers_path = tmp_path / "answers.json"
    _write_json(answers_path, _answers(profile="kept_profile"))
    _run_orchestrator_cli(monkeypatch, capsys, "init-config", "--vault", str(vault), "--answers-json", str(answers_path))
    raw_paper = vault / "_epi/raw" / "paper-a" / "paper.pdf"
    raw_paper.parent.mkdir(parents=True)
    raw_paper.write_text("paper", encoding="utf-8")
    transient_meta = vault / "_epi/meta" / "temporary.json"
    transient_meta.write_text("temporary", encoding="utf-8")

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "wiki-reset",
        "--vault",
        str(vault),
        "--confirmed-by",
        "确认重置 EPI wiki",
        "--backup-root",
        str(backup_root),
        "--json",
    )
    payload = json.loads(output)

    assert exit_code == 0
    assert payload["preserved_config"] is True
    assert "profile: kept_profile" in (vault / "_epi/meta" / "epi-config.yaml").read_text(encoding="utf-8")
    assert not raw_paper.exists()
    assert (backup_root / "_epi/raw" / "paper-a" / "paper.pdf").read_text(encoding="utf-8") == "paper"
    assert (backup_root / "_epi/meta" / "temporary.json").read_text(encoding="utf-8") == "temporary"
    assert (vault / "_epi/meta" / "wiki-reset").is_dir()


def test_wiki_reset_preview_lists_actions_without_mutating(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    answers_path = tmp_path / "answers.json"
    _write_json(answers_path, _answers(profile="preview_profile"))
    _run_orchestrator_cli(monkeypatch, capsys, "init-config", "--vault", str(vault), "--answers-json", str(answers_path))
    raw_paper = vault / "_epi/raw" / "paper-a" / "paper.pdf"
    raw_paper.parent.mkdir(parents=True)
    raw_paper.write_text("paper", encoding="utf-8")

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "wiki-reset",
        "--vault",
        str(vault),
        "--preview",
        "--json",
    )
    payload = json.loads(output)

    assert exit_code == 0
    assert payload["status"] == "preview"
    assert payload["preserve_config"] is True
    assert any(action["action"] == "would_backup" for action in payload["actions"])
    assert raw_paper.exists()
    assert "profile: preview_profile" in (vault / "_epi/meta" / "epi-config.yaml").read_text(encoding="utf-8")


def test_wiki_reset_requires_separate_config_confirmation(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    answers_path = tmp_path / "answers.json"
    _write_json(answers_path, _answers(profile="delete_me"))
    _run_orchestrator_cli(monkeypatch, capsys, "init-config", "--vault", str(vault), "--answers-json", str(answers_path))

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "wiki-reset",
        "--vault",
        str(vault),
        "--confirmed-by",
        "确认重置 EPI wiki",
        "--reset-config-confirmed-by",
        "确认同时重置 EPI config",
        "--no-backup",
        "--json",
    )
    payload = json.loads(output)

    assert exit_code == 0
    assert payload["reset_config"] is True
    assert payload["after_config"]["configured"] is False
    assert not (vault / "_epi/meta" / "epi-config.yaml").exists()
    assert (vault / "_epi/raw").is_dir()


def test_config_recover_lists_backup_candidates_and_restore_requires_confirmation(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    backup_root = tmp_path / "reset-backups"
    backup_config = backup_root / "old-run" / "_epi/meta" / "epi-config.yaml"
    backup_config.parent.mkdir(parents=True)
    backup_config.write_text("profile: recovered_profile\nbudget:\n  max_results: 9\n", encoding="utf-8")

    recover_exit, recover_output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "config-recover",
        "--vault",
        str(vault),
        "--backup-root",
        str(backup_root),
        "--json",
    )
    recover_payload = json.loads(recover_output)

    assert recover_exit == 0
    assert recover_payload["candidate_count"] == 1
    assert recover_payload["candidates"][0]["profile"] == "recovered_profile"
    assert "secret" not in recover_output.lower()

    restore_exit, restore_output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "config-restore",
        "--vault",
        str(vault),
        "--from",
        str(backup_config),
        "--confirmed-by",
        "确认恢复 EPI config",
        "--json",
    )
    restore_payload = json.loads(restore_output)

    assert restore_exit == 0
    assert restore_payload["status"] == "restored"
    assert "profile: recovered_profile" in (vault / "_epi/meta" / "epi-config.yaml").read_text(encoding="utf-8")
    state = json.loads((vault / "_epi/meta" / "epi-config-state.json").read_text(encoding="utf-8"))
    assert state["last_action"] == "config-restore"


def test_config_recover_prioritizes_current_and_history_before_backups(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    current = vault / "_epi/meta" / "epi-config.yaml"
    history = vault / "_epi/meta" / "config-history" / "old.yaml"
    backup = tmp_path / "reset-backups" / "old-run" / "_epi/meta" / "epi-config.yaml"
    current.parent.mkdir(parents=True)
    history.parent.mkdir(parents=True)
    backup.parent.mkdir(parents=True)
    current.write_text("profile: current_profile\n", encoding="utf-8")
    history.write_text("profile: history_profile\n", encoding="utf-8")
    backup.write_text("profile: backup_profile\n", encoding="utf-8")

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "config-recover",
        "--vault",
        str(vault),
        "--backup-root",
        str(tmp_path / "reset-backups"),
        "--json",
    )
    payload = json.loads(output)

    assert exit_code == 0
    assert [candidate["source_type"] for candidate in payload["candidates"][:3]] == [
        "current",
        "config-history",
        "provided-backup-root",
    ]


def test_wiki_repair_can_restore_missing_config_from_backup(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    backup_root = tmp_path / "reset-backups"
    backup_config = backup_root / "old-run" / "_epi/meta" / "epi-config.yaml"
    backup_config.parent.mkdir(parents=True)
    backup_config.write_text("profile: repair_profile\nbudget:\n  max_results: 13\n", encoding="utf-8")

    inspect_exit, inspect_output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "wiki-repair",
        "--vault",
        str(vault),
        "--backup-root",
        str(backup_root),
        "--json",
    )
    inspect_payload = json.loads(inspect_output)

    assert inspect_exit == 1
    assert inspect_payload["status"] == "inspected"
    assert inspect_payload["recovery"]["candidate_count"] == 1

    repair_exit, repair_output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "wiki-repair",
        "--vault",
        str(vault),
        "--backup-root",
        str(backup_root),
        "--restore-from",
        str(backup_config),
        "--confirmed-by",
        "确认恢复 EPI config",
        "--json",
    )
    repair_payload = json.loads(repair_output)

    assert repair_exit == 0
    assert repair_payload["status"] == "repaired"
    assert repair_payload["after_config"]["configured"] is True
    assert "profile: repair_profile" in (vault / "_epi/meta" / "epi-config.yaml").read_text(encoding="utf-8")
