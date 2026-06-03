import json
import sys

from epi.orchestrator import main, record_human_approval
from epi.wiki_ingest_handoff import build_wiki_ingest_handoff, render_wiki_ingest_handoff
from epi.wiki_ingest_trigger import build_wiki_ingest_trigger, render_wiki_ingest_trigger


EXPECTED_RESEARCH_WIKI_SKILLS = [
    "epi-paper-deposition",
    "llm-wiki",
    "wiki-ingest",
    "wiki-context-pack",
    "wiki-lint",
    "wiki-stage-commit",
    "wiki-status",
    "wiki-query",
    "wiki-provenance",
    "tag-taxonomy",
]

EXPECTED_FORMAL_PAGE_FAMILIES = [
    "references",
    "concepts",
    "derivations",
    "experiments",
    "synthesis",
    "reports",
    "opportunities",
]

EXPECTED_RESEARCH_REVIEW_FIELDS = [
    "theory_reconstruction",
    "formula_derivation",
    "figure_table_evidence",
    "novelty_type",
    "implementability",
    "reproducibility_risk",
    "research_gap",
    "cost_level",
]

EXPECTED_PAGE_LIFECYCLE_STATES = ["draft", "source-reviewed", "under-review", "verified"]


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _seed_agent_handoff(vault, slug="fixture-paper"):
    canonical_mineru_md = f"mineru/{slug}.md"
    paper_root = vault / "_epi" / "raw" / "papers" / slug
    staging_root = vault / "_epi" / "staging" / "papers" / slug
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
    (paper_root / "paper.pdf").write_bytes(b"%PDF-1.4\nfixture paper\n")
    mineru_dir = paper_root / "mineru"
    mineru_dir.mkdir(parents=True, exist_ok=True)
    (mineru_dir / f"{slug}.md").write_text(
        "# Abstract\n\nFixture paper abstract.\n\n## Method\n\nFixture paper method.\n",
        encoding="utf-8",
    )
    (mineru_dir / "paper.tex").write_text(
        "\\section{Method}\n\\begin{equation}y = x + 1\\end{equation}\n",
        encoding="utf-8",
    )
    image_dir = mineru_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    (image_dir / "figure-1.png").write_bytes(b"fixture-image")
    _write_json(
        mineru_dir / "mineru-manifest.json",
        {
            "outputs": [{"file_name": "paper.pdf", "state": "done", "image_count": 1}],
            "warnings": [],
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
        "evidence/source-reader.md",
        "briefs/reading-report.md",
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
            "final_source_review_contract": {
                "schema_version": "epi-final-source-review-contract-v1",
                "required": True,
                "suggested_output_path": "final-source-review.json",
                "required_artifacts": [
                    "paper.pdf",
                    "metadata.json",
                    canonical_mineru_md,
                    "mineru/paper.tex",
                    "mineru/images/*",
                    "mineru/mineru-manifest.json",
                ],
                "record_schema_version": "epi-final-source-review-v1",
                "required_wiki_skills": EXPECTED_RESEARCH_WIKI_SKILLS,
                "formal_page_families": EXPECTED_FORMAL_PAGE_FAMILIES,
                "research_review_fields": EXPECTED_RESEARCH_REVIEW_FIELDS,
                "page_lifecycle_states": EXPECTED_PAGE_LIFECYCLE_STATES,
            },
            "wiki_rule_source_model": {
                "execution_agent_policy": {
                    "allowed_executors": [
                        "Claude",
                        "Codex",
                        "other wiki-capable agents",
                    ],
                    "brand_neutrality": (
                        "Any wiki-capable agent may execute final writes if it follows the target vault "
                        "contract, source-first review, human approval, and final-source-review gates."
                    ),
                    "local_skills_role": "helpers, not authority",
                },
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
                "authority": "Resolve the target vault contract first.",
                "epi_write_scope": "internal-underscore-artifacts-only",
                "formal_routes_suggested": False,
                "wiki_batch_handoff_required": True,
                "required_wiki_skills": EXPECTED_RESEARCH_WIKI_SKILLS,
                "source_first_policy": f"Read {canonical_mineru_md}, mineru/paper.tex, mineru/images/*, and mineru/mineru-manifest.json before final wiki writing; reader outputs are navigation aids, not substitutes for the source paper.",
            },
            "formal_page_families": EXPECTED_FORMAL_PAGE_FAMILIES,
            "research_review_fields": EXPECTED_RESEARCH_REVIEW_FIELDS,
            "page_lifecycle_states": EXPECTED_PAGE_LIFECYCLE_STATES,
            "source_bundle": {
                "raw_artifacts": [
                    "paper.pdf",
                    "metadata.json",
                    canonical_mineru_md,
                    "mineru/paper.tex",
                    "mineru/images/*",
                    "mineru/mineru-manifest.json",
                ],
                "primary_source_reading_order": [
                    "metadata.json",
                    canonical_mineru_md,
                    "mineru/paper.tex",
                    "mineru/images/*",
                    "mineru/mineru-manifest.json",
                ],
                "formula_figure_review": {
                    "formulas": f"Review central formulas from {canonical_mineru_md} and mineru/paper.tex before distilling claims.",
                    "figures_tables_images": "Interpret figures, tables, and images from mineru/images/* instead of collapsing them into reader summary prose.",
                    "parse_uncertainty": "Inspect paper.pdf when MinerU parse limitations or missing figure/formula signals appear.",
                },
            },
            "formal_routes_suggested": False,
            "suggested_routes": [],
            "handoff_artifacts": [
                {"artifact_type": "source_reader", "target": "evidence/source-reader.md"},
                {"artifact_type": "reading_report", "target": "briefs/reading-report.md"},
            ],
            "candidate_topics": [],
            "candidate_clusters": [],
            "wiki_skill_handoff": {
                "batch_required": True,
                "required_skills": EXPECTED_RESEARCH_WIKI_SKILLS,
                "formal_page_families": EXPECTED_FORMAL_PAGE_FAMILIES,
                "page_lifecycle_states": EXPECTED_PAGE_LIFECYCLE_STATES,
            },
            "entrypoints": {
                "reading_report": "briefs/reading-report.md",
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
            "wiki_write_model": "wiki-skill-batch-distillation",
            "final_page_authority": "wiki-skill-batch-distillation",
            "epi_write_scope": "internal-underscore-artifacts-only",
            "formal_routes_suggested": False,
            "wiki_batch_handoff_required": True,
            "required_wiki_skills": EXPECTED_RESEARCH_WIKI_SKILLS,
            "formal_page_families": EXPECTED_FORMAL_PAGE_FAMILIES,
            "research_review_fields": EXPECTED_RESEARCH_REVIEW_FIELDS,
            "page_lifecycle_states": EXPECTED_PAGE_LIFECYCLE_STATES,
            "wiki_ingest_brief_path": str(brief_path),
            "agent_handoff_paths": [
                str(brief_path),
                str(staging_root / "briefs" / "reading-report.md"),
                str(staging_root / "evidence" / "source-reader.md"),
            ],
            "staged_evidence": [str(staging_root / "evidence" / "source-reader.md")],
            "staged_reports": [str(staging_root / "briefs" / "reading-report.md")],
            "suggested_route_targets": [],
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
    assert handoff["wiki_write_model"] == "wiki-skill-batch-distillation"
    assert handoff["ready_for_agent"] is False
    assert handoff["ready_after_human_approval"] is True
    assert handoff["paper_gate"]["action_required_checks"] == ["human-approval"]
    assert handoff["contract_files"]["AGENTS.md"]["present"] is True
    assert handoff["contract_files"]["_meta/schema.md"]["present"] is True
    assert handoff["contract_files"]["_meta/directory-structure.md"]["present"] is False
    assert handoff["local_skill_policy"] == "helpers-not-authority"
    assert handoff["formal_routes_suggested"] is False
    assert handoff["required_wiki_skills"] == EXPECTED_RESEARCH_WIKI_SKILLS
    assert handoff["formal_page_families"] == EXPECTED_FORMAL_PAGE_FAMILIES
    assert handoff["research_review_fields"] == EXPECTED_RESEARCH_REVIEW_FIELDS
    assert handoff["page_lifecycle_states"] == EXPECTED_PAGE_LIFECYCLE_STATES
    assert handoff["final_source_review_contract"]["required"] is True
    assert handoff["final_source_review_contract"]["suggested_output_path"] == "final-source-review.json"
    assert handoff["execution_agent_policy"]["allowed_executors"][:2] == ["Claude", "Codex"]
    assert "target vault contract" in handoff["execution_agent_policy"]["brand_neutrality"]
    assert handoff["agent_context_policy"]["delegation_model"] == "clean-worker-final-artifacts"
    assert "Codex may use subagents only when the user explicitly authorizes" in (
        handoff["agent_context_policy"]["codex_permission_note"]
    )
    assert handoff["agent_checklist"][0].startswith("Execution agent is neutral")
    assert any(item.startswith("Read target vault contract") for item in handoff["agent_checklist"])
    assert any("source-first rule" in item for item in handoff["agent_checklist"])
    assert any("mineru/fixture-paper.md" in item for item in handoff["agent_checklist"])
    assert any("mineru/images/*" in item for item in handoff["agent_checklist"])
    assert any("source paper artifacts" in item for item in handoff["agent_checklist"])
    assert any("figures, tables, and images" in item for item in handoff["agent_checklist"])
    assert any("final-source-review.json" in item for item in handoff["agent_checklist"])
    assert any("Search existing wiki pages" in item for item in handoff["agent_checklist"])
    assert any("Do not write final pages" in item for item in handoff["agent_checklist"])


def test_build_wiki_ingest_handoff_is_ready_after_recorded_human_approval(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)

    approval = record_human_approval(
        vault,
        slug,
        approved_by="codex-test",
        scope="run-wiki-ingest-agent",
    )
    handoff = build_wiki_ingest_handoff(vault, slug)

    assert handoff["ready_for_agent"] is True
    assert handoff["ready_after_human_approval"] is False
    assert handoff["paper_gate"]["conclusion"] == "success"
    assert handoff["paper_gate"]["action_required_checks"] == []
    assert handoff["paths"]["human_approval"] == approval["record_path"]
    assert any("Human approval is recorded" in item for item in handoff["agent_checklist"])


def test_wiki_ingest_trigger_requires_human_approval_before_agent_start(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)

    trigger = build_wiki_ingest_trigger(vault, slug)

    assert trigger["status"] == "action_required"
    assert trigger["ready_for_agent"] is False
    assert trigger["ready_after_human_approval"] is True
    assert trigger["next_action"] == "record-human-approval"
    assert "record-human-approval" in trigger["instruction"]
    assert not (vault / "_epi" / "staging" / "papers" / slug / "wiki-agent-trigger.json").exists()


def test_wiki_ingest_trigger_writes_agent_neutral_trigger_after_approval(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    record_human_approval(
        vault,
        slug,
        approved_by="codex-test",
        scope="run-wiki-ingest-agent",
    )

    trigger = build_wiki_ingest_trigger(vault, slug)
    trigger_path = vault / "_epi" / "staging" / "papers" / slug / "wiki-agent-trigger.json"
    stored = json.loads(trigger_path.read_text(encoding="utf-8"))

    assert trigger["schema_version"] == "epi-wiki-agent-trigger-v1"
    assert trigger["status"] == "ready"
    assert trigger["ready_for_agent"] is True
    assert trigger["next_action"] == "run-current-agent-as-wiki-ingest-agent"
    assert trigger["trigger_path"] == str(trigger_path)
    assert stored["schema_version"] == "epi-wiki-agent-trigger-v1"
    assert stored["next_action"] == "run-current-agent-as-wiki-ingest-agent"
    assert "Claude" in trigger["executor_policy"]["allowed_executors"]
    assert "Codex" in trigger["executor_policy"]["allowed_executors"]
    assert trigger["agent_context_policy"]["delegation_model"] == "clean-worker-final-artifacts"
    assert "Codex may use subagents only when the user explicitly authorizes" in (
        trigger["agent_context_policy"]["codex_permission_note"]
    )
    assert stored["agent_context_policy"] == trigger["agent_context_policy"]
    assert trigger["required_wiki_skills"] == EXPECTED_RESEARCH_WIKI_SKILLS
    assert "tag-taxonomy" in trigger["instruction"]
    assert "wiki-provenance" in trigger["instruction"]
    for family in ["derivations/", "experiments/", "opportunities/"]:
        assert family in trigger["instruction"]
    assert "final-source-review.json" in trigger["instruction"]
    assert "record-wiki-ingest" in trigger["instruction"]
    assert "briefs" in trigger["paths"]["reading_report"]
    assert "reading-report.md" in trigger["paths"]["reading_report"]
    assert trigger["paths"]["wiki_ingest_brief"].endswith("wiki-ingest-brief.json")
    assert any("No reader claim map is required" in item for item in trigger["agent_checklist"])
    assert any("paper.pdf" in item and "MinerU" in item for item in trigger["agent_checklist"])
    assert not (vault / "references").exists()


def test_render_wiki_ingest_trigger_shows_resume_command_after_approval(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    record_human_approval(
        vault,
        slug,
        approved_by="codex-test",
        scope="run-wiki-ingest-agent",
    )

    output = render_wiki_ingest_trigger(build_wiki_ingest_trigger(vault, slug))

    assert "# EPI Wiki Agent Trigger - fixture-paper" in output
    assert "ready_for_agent: true" in output
    assert "next_action: run-current-agent-as-wiki-ingest-agent" in output
    assert "wiki-provenance" in output
    assert "tag-taxonomy" in output
    assert "derivations/" in output
    assert "experiments/" in output
    assert "opportunities/" in output
    assert "record-wiki-ingest" in output
    assert "## Agent Context Policy" in output
    assert "Codex may use subagents only when the user explicitly authorizes" in output


def test_render_wiki_ingest_handoff_is_actionable_without_writing(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)

    output = render_wiki_ingest_handoff(build_wiki_ingest_handoff(vault, slug))

    assert "# EPI Wiki Ingest Handoff - fixture-paper" in output
    assert "next_action: run-wiki-ingest-agent" in output
    assert "ready_for_agent: false" in output
    assert "ready_after_human_approval: true" in output
    assert "## Execution Agent Policy" in output
    assert "allowed_executors: Claude, Codex, other wiki-capable agents" in output
    assert "## Agent Context Policy" in output
    assert "clean-worker-final-artifacts" in output
    assert "Codex may use subagents only when the user explicitly authorizes" in output
    assert "local skills: helpers-not-authority" in output
    assert "- AGENTS.md: present" in output
    assert "- _meta/directory-structure.md: missing" in output
    assert "Ar9av/obsidian-wiki" in output
    assert "kepano/obsidian-skills" in output
    assert "local llm-wiki / wiki-ingest / obsidian-markdown skills" in output
    assert "tag-taxonomy" in output
    assert "Do not write final pages from EPI suggested routes directly" in output
    assert "## Final Source Review" in output
    assert "suggested_output_path: final-source-review.json" in output
    assert "mineru/fixture-paper.md" in output
    assert "mineru/images/*" in output
    assert "source paper artifacts" in output
    assert "derivations/" in output
    assert "experiments/" in output
    assert "opportunities/" in output


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
    assert payload["final_source_review_contract"]["required"] is True
