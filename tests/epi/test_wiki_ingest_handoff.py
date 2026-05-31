import json
import sys

from epi.orchestrator import main
from epi.wiki_ingest_handoff import build_wiki_ingest_handoff, render_wiki_ingest_handoff


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _seed_agent_handoff(vault, slug="fixture-paper"):
    paper_root = vault / "_raw" / "papers" / slug
    staging_root = vault / "_staging" / "papers" / slug
    paper_root.mkdir(parents=True, exist_ok=True)
    staging_root.mkdir(parents=True, exist_ok=True)
    _write_json(
        paper_root / "metadata.json",
        {
            "slug": slug,
            "title": "Fixture Paper",
            "doi": "10.1000/fixture",
            "venue": "IROS",
        },
    )
    _write_json(
        paper_root / "critic" / "critic-report.json",
        {
            "outcome": "pass",
            "next_action": "stage",
            "hard_rule": "No critic pass, no compiled wiki write.",
            "reviewer_quorum_path": str(paper_root / "critic" / "critic-quorum.json"),
        },
    )
    _write_json(
        paper_root / "critic" / "critic-quorum.json",
        {
            "final_outcome": "pass",
            "disagreement": False,
            "reviewers": [{"name": "paper-quality-critic", "verdict": "pass"}],
        },
    )
    for relative in [
        "references/fixture-paper.md",
        "concepts/fixture-paper-concept.md",
        "synthesis/fixture-paper-synthesis.md",
        "reports/fixture-paper-reading-report.md",
    ]:
        path = staging_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {path.stem}\n", encoding="utf-8")
    brief_path = staging_root / "wiki-ingest-brief.json"
    _write_json(
        brief_path,
        {
            "schema_version": "epi-wiki-ingest-brief-v1",
            "handoff_type": "agent-mediated-wiki-ingest",
            "paper_slug": slug,
            "title": "Fixture Paper",
            "trust_status": {"status": "accepted", "read_mode": "Use report first."},
            "wiki_framework_references": [
                {"name": "Ar9av/obsidian-wiki"},
                {"name": "kepano/obsidian-skills"},
                {"name": "initiatione/obsidian-wiki-dev"},
            ],
            "wiki_rule_source_model": {
                "resolution_order": [
                    {"source": "current user instruction", "role": "session goal"},
                    {"source": "target vault AGENTS.md", "role": "owner contract"},
                    {"source": "_meta/schema.md", "role": "routing"},
                    {"source": "_meta/taxonomy.md", "role": "taxonomy"},
                    {"source": "Ar9av/obsidian-wiki", "role": "framework"},
                    {"source": "kepano/obsidian-skills", "role": "format"},
                    {"source": "initiatione/obsidian-wiki-dev", "role": "personalized rules"},
                    {
                        "source": "local llm-wiki / wiki-ingest / obsidian-markdown skills",
                        "role": "execution adapters",
                    },
                ],
                "must_read_before_final_write": [
                    "target vault AGENTS.md",
                    "_meta/agent-operating-contract.md",
                    "_meta/schema.md",
                    "_meta/taxonomy.md",
                    "_meta/directory-structure.md",
                    "index.md",
                    "log.md",
                    ".manifest.json",
                ],
                "write_contract_requirements": [
                    "Keep Markdown vault files as the source of truth.",
                    "Search existing pages before creating duplicates.",
                    "Final wiki pages must be grounded in the source paper artifacts, not reader summaries alone.",
                ],
            },
            "ingest_policy": {
                "suggested_routes_only": True,
                "authority": "Resolve the target vault contract first.",
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
                "primary_source_reading_order": [
                    "metadata.json",
                    "mineru/paper.md",
                    "mineru/paper.tex",
                    "mineru/images/*",
                    "mineru/mineru-manifest.json",
                ],
                "formula_figure_review": {
                    "formulas": "Review central formulas from mineru/paper.md and mineru/paper.tex before distilling claims.",
                    "figures_tables_images": "Interpret figures, tables, and images from mineru/images/* instead of collapsing them into reader summary prose.",
                    "parse_uncertainty": "Inspect paper.pdf when MinerU parse limitations or missing figure/formula signals appear.",
                },
            },
            "suggested_routes": [
                {"page_type": "reference", "target": "references/fixture-paper.md"},
                {"page_type": "concept", "target": "concepts/fixture-paper-concept.md"},
            ],
            "entrypoints": {
                "reading_report": "reports/fixture-paper-reading-report.md",
                "evidence_map": "reader/evidence-map.json",
            },
        },
    )
    _write_json(
        staging_root / "promotion-plan.json",
        {
            "paper_slug": slug,
            "critic_outcome": "pass",
            "handoff_type": "agent-mediated-wiki-ingest",
            "wiki_write_model": "agent-mediated-vault-contract",
            "final_page_authority": "target-vault-contract-and-wiki-ingest-agent",
            "wiki_ingest_brief_path": str(brief_path),
            "agent_handoff_paths": [
                str(brief_path),
                str(staging_root / "reports" / "fixture-paper-reading-report.md"),
            ],
            "staged_reference": str(staging_root / "references" / "fixture-paper.md"),
            "staged_concepts": [str(staging_root / "concepts" / "fixture-paper-concept.md")],
            "staged_synthesis": [str(staging_root / "synthesis" / "fixture-paper-synthesis.md")],
            "staged_reports": [str(staging_root / "reports" / "fixture-paper-reading-report.md")],
        },
    )
    (vault / "AGENTS.md").write_text("# Vault Contract\n", encoding="utf-8")
    (vault / "_meta").mkdir(parents=True, exist_ok=True)
    (vault / "_meta" / "schema.md").write_text("# Schema\n", encoding="utf-8")
    (vault / "_meta" / "taxonomy.md").write_text("# Taxonomy\n", encoding="utf-8")
    return slug


def _run_orchestrator_cli(monkeypatch, capsys, *args):
    monkeypatch.setattr(sys, "argv", ["epi.orchestrator", *args])
    exit_code = main()
    output = capsys.readouterr().out
    return exit_code, output


def test_build_wiki_ingest_handoff_resolves_contract_and_agent_checklist(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)

    handoff = build_wiki_ingest_handoff(vault, slug)

    assert handoff["paper_slug"] == slug
    assert handoff["paper_gate"]["next_action"] == "run-wiki-ingest-agent"
    assert handoff["wiki_write_model"] == "agent-mediated-vault-contract"
    assert handoff["ready_for_agent"] is False
    assert handoff["ready_after_human_approval"] is True
    assert handoff["paper_gate"]["action_required_checks"] == ["human-approval"]
    assert handoff["contract_files"]["AGENTS.md"]["present"] is True
    assert handoff["contract_files"]["_meta/schema.md"]["present"] is True
    assert handoff["contract_files"]["_meta/directory-structure.md"]["present"] is False
    assert handoff["local_skill_policy"] == "helpers-not-authority"
    assert handoff["suggested_routes_only"] is True
    assert "source-first rule" in handoff["agent_checklist"][2]
    assert any("mineru/paper.md" in item for item in handoff["agent_checklist"])
    assert any("mineru/images/*" in item for item in handoff["agent_checklist"])
    assert any("source paper artifacts" in item for item in handoff["agent_checklist"])
    assert any("figures, tables, and images" in item for item in handoff["agent_checklist"])
    assert handoff["agent_checklist"][0].startswith("Read target vault contract files")
    assert any("Search existing wiki pages" in item for item in handoff["agent_checklist"])
    assert any("Do not write final pages" in item for item in handoff["agent_checklist"])


def test_render_wiki_ingest_handoff_is_actionable_without_writing(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)

    output = render_wiki_ingest_handoff(build_wiki_ingest_handoff(vault, slug))

    assert "# EPI Wiki Ingest Handoff - fixture-paper" in output
    assert "next_action: run-wiki-ingest-agent" in output
    assert "ready_for_agent: false" in output
    assert "ready_after_human_approval: true" in output
    assert "local skills: helpers-not-authority" in output
    assert "- AGENTS.md: present" in output
    assert "- _meta/directory-structure.md: missing" in output
    assert "Ar9av/obsidian-wiki" in output
    assert "kepano/obsidian-skills" in output
    assert "local llm-wiki / wiki-ingest / obsidian-markdown skills" in output
    assert "Do not write final pages from EPI suggested routes directly." in output
    assert "mineru/paper.md" in output
    assert "mineru/images/*" in output
    assert "source paper artifacts" in output


def test_wiki_ingest_handoff_cli_outputs_json(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "wiki-ingest-handoff",
        "--vault",
        str(vault),
        "--slug",
        slug,
        "--json",
    )

    payload = json.loads(output)
    assert exit_code == 0
    assert payload["paper_slug"] == slug
    assert payload["ready_for_agent"] is False
    assert payload["ready_after_human_approval"] is True
    assert payload["paper_gate"]["next_action"] == "run-wiki-ingest-agent"
    assert payload["contract_files"]["AGENTS.md"]["present"] is True
