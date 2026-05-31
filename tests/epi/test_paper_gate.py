import json
import sys

from epi.orchestrator import main
from epi.paper_gate import build_paper_gate, render_paper_gate


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _seed_paper_gate_fixture(vault, slug, *, critic_outcome="pass", staged=True, promoted=False, agent_handoff=False):
    paper_root = vault / "_raw" / "papers" / slug
    staging_root = vault / "_staging" / "papers" / slug
    critic_root = paper_root / "critic"
    critic_root.mkdir(parents=True, exist_ok=True)
    _write_json(
        paper_root / "metadata.json",
        {
            "slug": slug,
            "title": "Fixture Paper",
            "doi": "10.1000/fixture",
        },
    )
    quorum = {
        "stage": "critic-quorum",
        "final_outcome": critic_outcome,
        "reviewers": [
            {"name": "paper-quality-critic", "verdict": critic_outcome},
            {"name": "peer-review-methods-critic", "verdict": critic_outcome},
        ],
    }
    _write_json(critic_root / "critic-quorum.json", quorum)
    _write_json(
        critic_root / "critic-report.json",
        {
            "outcome": critic_outcome,
            "next_action": "stage" if critic_outcome == "pass" else "revise-reader",
            "hard_rule": "No critic pass, no compiled wiki write.",
            "reviewer_quorum_path": str(critic_root / "critic-quorum.json"),
        },
    )
    if staged:
        reference_path = staging_root / "references" / f"{slug}.md"
        concept_path = staging_root / "concepts" / f"{slug}-concept.md"
        synthesis_path = staging_root / "synthesis" / f"{slug}-synthesis.md"
        report_path = staging_root / "reports" / f"{slug}-reading-report.md"
        for path in [reference_path, concept_path, synthesis_path, report_path]:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"# {path.stem}\n", encoding="utf-8")
        plan = {
            "paper_slug": slug,
            "critic_outcome": critic_outcome,
            "staged_reference": str(reference_path),
            "staged_concepts": [str(concept_path)],
            "staged_synthesis": [str(synthesis_path)],
            "staged_reports": [str(report_path)],
        }
        if agent_handoff:
            brief_path = staging_root / "wiki-ingest-brief.json"
            _write_json(
                brief_path,
                {
                    "schema_version": "epi-wiki-ingest-brief-v1",
                    "handoff_type": "agent-mediated-wiki-ingest",
                    "wiki_framework_references": [
                        {"name": "Ar9av/obsidian-wiki"},
                        {"name": "kepano/obsidian-skills"},
                        {"name": "initiatione/obsidian-wiki-dev"},
                    ],
                    "wiki_rule_source_model": {
                        "resolution_order": [
                            {"source": "target vault AGENTS.md", "role": "vault owner contract"},
                            {"source": "_meta/schema.md", "role": "routing and schema"},
                            {"source": "Ar9av/obsidian-wiki", "role": "wiki framework"},
                            {"source": "kepano/obsidian-skills", "role": "Obsidian syntax"},
                            {"source": "initiatione/obsidian-wiki-dev", "role": "personalized rules"},
                            {
                                "source": "local llm-wiki / wiki-ingest / obsidian-markdown skills",
                                "role": "installed adapters",
                            },
                        ],
                        "write_contract_requirements": [
                            "Keep Markdown vault files as the source of truth.",
                            "Final wiki pages must be grounded in the source paper artifacts, not reader summaries alone.",
                            "Review central formulas, figures, tables, and image evidence before distilling reusable wiki claims.",
                        ],
                    },
                    "ingest_policy": {
                        "suggested_routes_only": True,
                        "source_first_policy": "Read mineru/paper.md, mineru/paper.tex, mineru/images/*, and mineru/mineru-manifest.json before final wiki writing; reader outputs are navigation aids, not substitutes for the source paper.",
                    },
                    "source_bundle": {
                        "raw_artifacts": [
                            "paper.pdf",
                            "metadata.json",
                            "mineru/paper.md",
                            "mineru/paper.tex",
                            "mineru/images/*",
                            "mineru/mineru-manifest.json",
                        ],
                        "formula_figure_review": {
                            "formulas": "Review central formulas before distilling claims.",
                            "figures_tables_images": "Interpret figures/tables/images from mineru/images/*.",
                            "parse_uncertainty": "Inspect paper.pdf when parse limitations appear.",
                        },
                    },
                },
            )
            plan.update(
                {
                    "handoff_type": "agent-mediated-wiki-ingest",
                    "wiki_write_model": "agent-mediated-vault-contract",
                    "final_page_authority": "target-vault-contract-and-wiki-ingest-agent",
                    "wiki_ingest_brief_path": str(brief_path),
                    "agent_handoff_paths": [str(brief_path), str(report_path)],
                }
            )
        else:
            plan["compiled_targets"] = [
                f"references/{slug}.md",
                f"concepts/{slug}-concept.md",
                f"synthesis/{slug}-synthesis.md",
                f"reports/{slug}-reading-report.md",
            ]
        _write_json(staging_root / "promotion-plan.json", plan)
    if promoted:
        _write_json(
            paper_root / "promotion-record.json",
            {
                "status": "promoted",
                "human_gate_decision": {"status": "approved", "approved_by": "codex-test"},
            },
        )
    return paper_root


def _run_orchestrator_cli(monkeypatch, capsys, *args):
    monkeypatch.setattr(sys, "argv", ["epi.orchestrator", *args])
    exit_code = main()
    output = capsys.readouterr().out
    return exit_code, output


def test_paper_gate_reports_ready_paper_waiting_for_human_approval(tmp_path):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    _seed_paper_gate_fixture(vault, slug)

    gate = build_paper_gate(vault, slug)

    assert gate["status"] == "waiting_for_human_gate"
    assert gate["check_suite"]["conclusion"] == "action_required"
    assert gate["next_action"] == "promote-to-wiki"
    checks = {run["name"]: run["conclusion"] for run in gate["check_suite"]["check_runs"]}
    assert checks["critic-report"] == "success"
    assert checks["critic-outcome"] == "success"
    assert checks["critic-quorum"] == "success"
    assert checks["promotion-plan"] == "success"
    assert checks["staged-drafts"] == "success"
    assert checks["compiled-targets"] == "success"
    assert checks["human-approval"] == "action_required"

    rendered = render_paper_gate(gate)
    assert "# EPI Paper Gate - fixture-paper" in rendered
    assert "next: promote-to-wiki" in rendered
    assert "human-approval: action_required" in rendered


def test_paper_gate_reports_agent_handoff_ready_for_wiki_ingest(tmp_path):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    _seed_paper_gate_fixture(vault, slug, agent_handoff=True)

    gate = build_paper_gate(vault, slug)

    assert gate["status"] == "waiting_for_human_gate"
    assert gate["check_suite"]["conclusion"] == "action_required"
    assert gate["next_action"] == "run-wiki-ingest-agent"
    checks = {run["name"]: run["conclusion"] for run in gate["check_suite"]["check_runs"]}
    assert checks["wiki-ingest-brief"] == "success"
    assert checks["final-wiki-authority"] == "success"
    assert checks["human-approval"] == "action_required"
    assert "compiled-targets" not in checks


def test_paper_gate_blocks_agent_handoff_without_wiki_rule_source_model(tmp_path):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    _seed_paper_gate_fixture(vault, slug, agent_handoff=True)
    brief_path = vault / "_staging" / "papers" / slug / "wiki-ingest-brief.json"
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    del brief["wiki_rule_source_model"]
    brief_path.write_text(json.dumps(brief), encoding="utf-8")

    gate = build_paper_gate(vault, slug)

    assert gate["status"] == "blocked"
    assert gate["next_action"] == "repair-gate-failures"
    checks = {run["name"]: run for run in gate["check_suite"]["check_runs"]}
    assert checks["wiki-ingest-brief"]["conclusion"] == "failure"
    assert "wiki_rule_source_model is missing" in checks["wiki-ingest-brief"]["output"]["summary"]
    assert "human-approval" not in checks


def test_paper_gate_blocks_agent_handoff_without_source_first_artifacts(tmp_path):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    _seed_paper_gate_fixture(vault, slug, agent_handoff=True)
    brief_path = vault / "_staging" / "papers" / slug / "wiki-ingest-brief.json"
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["source_bundle"]["raw_artifacts"].remove("mineru/images/*")
    brief_path.write_text(json.dumps(brief), encoding="utf-8")

    gate = build_paper_gate(vault, slug)

    assert gate["status"] == "blocked"
    checks = {run["name"]: run for run in gate["check_suite"]["check_runs"]}
    assert checks["wiki-ingest-brief"]["conclusion"] == "failure"
    assert "source-first raw artifacts are incomplete" in checks["wiki-ingest-brief"]["output"]["summary"]
    assert "human-approval" not in checks


def test_paper_gate_blocks_plan_without_compiled_targets(tmp_path):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    _seed_paper_gate_fixture(vault, slug)
    plan_path = vault / "_staging" / "papers" / slug / "promotion-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    del plan["compiled_targets"]
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    gate = build_paper_gate(vault, slug)

    assert gate["status"] == "blocked"
    assert gate["check_suite"]["conclusion"] == "failure"
    assert gate["next_action"] == "repair-gate-failures"
    checks = {run["name"]: run for run in gate["check_suite"]["check_runs"]}
    assert checks["compiled-targets"]["conclusion"] == "failure"
    assert "compiled_targets" in checks["compiled-targets"]["output"]["summary"]
    assert "human-approval" not in checks


def test_paper_gate_blocks_nonpassing_critic_before_staging_or_promotion(tmp_path):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    _seed_paper_gate_fixture(vault, slug, critic_outcome="revise-reader", staged=False)

    gate = build_paper_gate(vault, slug)

    assert gate["status"] == "blocked"
    assert gate["check_suite"]["conclusion"] == "failure"
    assert gate["next_action"] == "revise-reader"
    checks = {run["name"]: run["conclusion"] for run in gate["check_suite"]["check_runs"]}
    assert checks["critic-report"] == "success"
    assert checks["critic-outcome"] == "failure"
    assert checks["promotion-plan"] == "action_required"
    assert "human-approval" not in checks


def test_paper_gate_cli_outputs_json(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    _seed_paper_gate_fixture(vault, slug)

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "paper-gate",
        "--vault",
        str(vault),
        "--slug",
        slug,
        "--json",
    )

    payload = json.loads(output)
    assert exit_code == 0
    assert payload["paper_slug"] == slug
    assert payload["check_suite"]["conclusion"] == "action_required"
