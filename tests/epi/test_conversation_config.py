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
    assert payload["config_path"].endswith("_meta\\epi-config.yaml") or payload["config_path"].endswith("_meta/epi-config.yaml")


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

    config_path = vault / "_meta" / "epi-config.yaml"
    state_path = vault / "_meta" / "epi-config-state.json"
    history_files = list((vault / "_meta" / "config-history").glob("*.yaml"))
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
    before = (vault / "_meta" / "epi-config.yaml").read_text(encoding="utf-8")

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
    after_propose = (vault / "_meta" / "epi-config.yaml").read_text(encoding="utf-8")

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
    config_text = (vault / "_meta" / "epi-config.yaml").read_text(encoding="utf-8")
    history_files = list((vault / "_meta" / "config-history").glob("*.yaml"))

    assert apply_exit == 0
    assert "config_updated=true" in apply_output
    assert "max_results: 29" in config_text
    assert "enabled: true" in config_text
    assert len(history_files) == 2


def test_reset_update_preserves_existing_wiki_artifacts(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    for relative in [
        "_raw/papers/keep/paper.pdf",
        "_runs/keep-run/run-state.json",
        "_staging/papers/keep/promotion-plan.json",
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
    assert "profile: reset_profile" in (vault / "_meta" / "epi-config.yaml").read_text(encoding="utf-8")
    assert (vault / "_raw/papers/keep/paper.pdf").read_text(encoding="utf-8") == "keep"
    assert (vault / "_runs/keep-run/run-state.json").read_text(encoding="utf-8") == "keep"
    assert (vault / "_staging/papers/keep/promotion-plan.json").read_text(encoding="utf-8") == "keep"
    assert (vault / "references/keep.md").read_text(encoding="utf-8") == "keep"
