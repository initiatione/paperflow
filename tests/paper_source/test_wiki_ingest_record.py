import json
import importlib
import sys

import pytest

from paper_source.artifacts import file_sha256
from paper_source import orchestrator as orchestrator_module
from paper_source.orchestrator import main, record_human_approval, record_wiki_ingest
from paper_source.paper_gate import build_paper_gate
from paper_source.wiki_ingest_record import (
    LEGACY_PRW_RECORD_REQUEST_SCHEMA_VERSION,
    PAPER_WIKI_RECORD_REQUEST_SCHEMA_VERSION,
    PRW_RECORD_REQUEST_SCHEMA_VERSION,
    create_wiki_ingest_record,
)


EXPECTED_RESEARCH_WIKI_SKILLS = [
    "paper-research-wiki",
    "paper-source-paper-deposition",
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

EXPECTED_FORMAL_PAGE_FAMILIES = [
    "references",
    "concepts",
    "derivations",
    "experiments",
    "synthesis",
    "reports",
    "opportunities",
]

EXPECTED_PAGE_LIFECYCLE_STATES = ["draft"]

EXPECTED_GOVERNANCE_LAYERS = [
    {
        "layer": "obsidian_syntax",
        "source": "kepano/obsidian-skills",
        "owns": [
            "YAML properties/frontmatter",
            "tags and aliases",
            "wikilinks",
            "Markdown links",
            "embeds",
            "callouts",
            "Obsidian math delimiters",
            "bases and canvas syntax",
        ],
    },
    {
        "layer": "paper_wiki_evidence",
        "source": "paper-research-wiki",
        "owns": [
            "source-grounded paper claims",
            "formal page families",
            "formula reasoning chains",
            "figure/table evidence cards",
            "formal page relationships",
            "evidence tiers",
            "final-source-review.json readiness",
        ],
    },
    {
        "layer": "local_vault_governance",
        "source": "target vault AGENTS.md and _meta/*",
        "owns": [
            "local taxonomy",
            "page ownership",
            "staged writes",
            "QMD scope",
            "migration and retirement policy",
        ],
    },
]


def test_prw_schema_alias_points_to_current_paper_wiki_contract():
    assert PRW_RECORD_REQUEST_SCHEMA_VERSION == PAPER_WIKI_RECORD_REQUEST_SCHEMA_VERSION
    assert PRW_RECORD_REQUEST_SCHEMA_VERSION != LEGACY_PRW_RECORD_REQUEST_SCHEMA_VERSION


def test_orchestrator_reexports_wiki_record_workflow_entrypoints():
    wiki_record_workflows = importlib.import_module("paper_source.wiki_record_workflows")

    assert orchestrator_module.record_human_approval is wiki_record_workflows.record_human_approval
    assert orchestrator_module.record_wiki_ingest is wiki_record_workflows.record_wiki_ingest
    assert orchestrator_module._write_promotion_or_rollback_run_state is (
        wiki_record_workflows._write_promotion_or_rollback_run_state
    )
    assert orchestrator_module._write_promotion_routed_report is wiki_record_workflows._write_promotion_routed_report
    assert orchestrator_module._write_rollback_routed_report is wiki_record_workflows._write_rollback_routed_report


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _seed_agent_handoff(vault, slug="fixture-paper"):
    canonical_mineru_md = f"mineru/{slug}.md"
    paper_root = vault / "_paper_source" / "raw" / slug
    staging_root = vault / "_paper_source" / "staging" / "papers" / slug
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
            "schema_version": "paper-source-wiki-ingest-brief-v1",
            "handoff_type": "agent-mediated-wiki-ingest",
            "paper_slug": slug,
            "title": "Fixture Paper",
            "wiki_framework_references": [
                {"name": "Ar9av/obsidian-wiki"},
                {"name": "kepano/obsidian-skills"},
                {"name": "initiatione/obsidian-wiki-dev"},
            ],
            "final_source_review_contract": {
                "schema_version": "paper-source-final-source-review-contract-v1",
                "required": True,
                "suggested_output_path": "final-source-review.json",
                "required_artifacts": [
                    "paper.pdf",
                    "metadata.json",
                    canonical_mineru_md,
                    "mineru/images/*",
                    "mineru/mineru-manifest.json",
                ],
                "record_schema_version": "paper-source-final-source-review-v1",
                "required_wiki_skills": EXPECTED_RESEARCH_WIKI_SKILLS,
                "formal_page_families": EXPECTED_FORMAL_PAGE_FAMILIES,
                "research_review_fields": EXPECTED_RESEARCH_REVIEW_FIELDS,
                "page_lifecycle_states": EXPECTED_PAGE_LIFECYCLE_STATES,
            },
            "wiki_rule_source_model": {
                "governance_layers": EXPECTED_GOVERNANCE_LAYERS,
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
                    {"source": "target vault AGENTS.md", "role": "owner contract"},
                    {"source": "_meta/schema.md", "role": "routing"},
                    {
                        "source": "paper-research-wiki (Paper Wiki canonical paper wiki layer)",
                        "role": "canonical paper wiki workflow layer; paper-source-paper-deposition remains compatibility adapter",
                    },
                    {"source": "Ar9av/obsidian-wiki", "role": "framework"},
                    {"source": "kepano/obsidian-skills", "role": "format"},
                    {"source": "initiatione/obsidian-wiki-dev", "role": "personalized rules"},
                    {
                        "source": "local llm-wiki / wiki-ingest / obsidian-markdown skills",
                        "role": "execution adapters",
                    },
                ],
                "write_contract_requirements": [
                    "Keep Markdown vault files as the source of truth.",
                    "Search existing pages before creating duplicates.",
                    "Final wiki pages must be grounded in the source paper artifacts, not reader summaries alone.",
                    "Use MinerU Markdown as the primary source for formulas, notation, method context, and prose; missing native TeX is normal and must not block writing or recording.",
                    "Use paper.pdf, formula-index.json, figure-index.json, and image evidence only when MinerU Markdown is missing, wrong, ambiguous, or insufficient.",
                ],
            },
            "ingest_policy": {
                "authority": "Resolve the target vault contract first.",
                "paper_source_write_scope": "internal-underscore-artifacts-only",
                "formal_routes_suggested": False,
                "wiki_batch_handoff_required": True,
                "required_wiki_skills": EXPECTED_RESEARCH_WIKI_SKILLS,
                "source_first_policy": (
                    f"Read {canonical_mineru_md}, mineru/images/*, mineru/mineru-manifest.json, "
                    "figure-index.json, and formula-index.json before final wiki writing. "
                    "Use MinerU Markdown as the primary formula and notation source; fall back to "
                    "paper.pdf, formula-index.json, figure-index.json, or image evidence only when "
                    "Markdown is missing, wrong, ambiguous, or insufficient. Missing native TeX is normal "
                    "and must not block writing or recording. Reader outputs are navigation aids, "
                    "not substitutes for the source paper."
                ),
            },
            "formal_page_families": EXPECTED_FORMAL_PAGE_FAMILIES,
            "research_review_fields": EXPECTED_RESEARCH_REVIEW_FIELDS,
            "page_lifecycle_states": EXPECTED_PAGE_LIFECYCLE_STATES,
            "formal_routes_suggested": False,
            "suggested_routes": [],
            "handoff_artifacts": [
                {"artifact_type": "source_reader", "target": "evidence/source-reader.md"},
                {"artifact_type": "reading_report", "target": "briefs/reading-report.md"},
            ],
            "source_bundle": {
                "raw_artifacts": [
                    "paper.pdf",
                    "metadata.json",
                    canonical_mineru_md,
                    "mineru/images/*",
                    "mineru/mineru-manifest.json",
                    "figure-index.json",
                    "formula-index.json",
                ],
                "formula_figure_review": {
                    "formulas": (
                        "Use MinerU Markdown as the primary formula and notation source; fall back "
                        "to paper.pdf, formula-index.json, figure-index.json, or image evidence only "
                        "when Markdown is missing, wrong, ambiguous, or insufficient. Missing native TeX "
                        "is normal and must not block writing or recording."
                    ),
                    "figures_tables_images": "Interpret each figure, table, and image from mineru/images/* with figure-index.json.",
                    "parse_uncertainty": "Inspect paper.pdf only when Markdown/index evidence is ambiguous.",
                },
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
            "paper_source_write_scope": "internal-underscore-artifacts-only",
            "formal_routes_suggested": False,
            "wiki_batch_handoff_required": True,
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
    return slug


def _write_final_page(vault, relative, content):
    path = vault / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _formal_page_content(family, title, *, body=None):
    body = body or (
        f"# {title}\n\n"
        "这页把 source-backed claims 连接到 [[concepts/fixture-method-family]]，并保留证据路径。\n\n"
        "## 模型与方法\n\n"
        "方法部分记录 source bundle 中的 method、assumption 和 control variable。\n\n"
        "## 关键公式\n\n"
        "$$y = x + 1$$\n\n"
        "## 实验与指标\n\n"
        "实验部分记录 baseline、metric 和 evaluation setting。\n\n"
        "## 局限\n\n"
        "局限和 caveat 继续绑定到 source artifacts。\n"
    )
    return (
        "---\n"
        f'title: "{title}"\n'
        f"category: {family}\n"
        f"page_family: {family}\n"
        "tags: [paper-source, fixture]\n"
        "aliases: []\n"
        f'sources: ["{_obsidian_uri_pdf_source(title=title)}"]\n'
        "source_id: fixture-paper\n"
        f'summary: "Source-grounded {family} page for fixture validation."\n'
        "provenance:\n"
        "  extracted: [\"mineru/fixture-paper.md#method\"]\n"
        "  inferred: []\n"
        "  ambiguous: []\n"
        "base_confidence: high\n"
        "lifecycle: draft\n"
        "lifecycle_changed: 2026-06-03\n"
        "tier: source\n"
        "created: 2026-06-03\n"
        "updated: 2026-06-03\n"
        "---\n\n"
        "## 原文与证据入口\n\n"
        f"- [{title}]({_obsidian_uri_pdf_url()})\n\n"
        + body
    )


def _obsidian_uri_pdf_url(slug="fixture-paper"):
    return f"obsidian://open?vault=paper-research-wiki&file=_paper_source%2Fraw%2F{slug}%2Fpaper.pdf"


def _legacy_obsidian_uri_pdf_url(slug="fixture-paper"):
    return f"obsidian://open?vault=paper-research-wiki&file=_epi%2Fraw%2F{slug}%2Fpaper.pdf"


def _obsidian_uri_pdf_source(slug="fixture-paper", title="Fixture Paper"):
    return f"[{title}]({_obsidian_uri_pdf_url(slug)})"


def _source_artifact_record(paper_root, artifact):
    path = paper_root / artifact
    return {
        "artifact": artifact,
        "status": "reviewed",
        "sha256": file_sha256(path),
    }


def _write_final_source_review(vault, slug, pages):
    paper_root = vault / "_paper_source" / "raw" / slug
    staging_root = vault / "_paper_source" / "staging" / "papers" / slug
    canonical_mineru_md = f"mineru/{slug}.md"
    image_files = sorted((paper_root / "mineru" / "images").glob("*"))
    payload = {
        "schema_version": "paper-source-final-source-review-v1",
        "paper_slug": slug,
        "reviewed_artifacts": [
            _source_artifact_record(paper_root, "paper.pdf"),
            _source_artifact_record(paper_root, "metadata.json"),
            _source_artifact_record(paper_root, canonical_mineru_md),
            {
                "artifact": "mineru/images/*",
                "status": "reviewed",
                "file_count": len(image_files),
                "files": [
                    {
                        "relative_path": image.relative_to(paper_root).as_posix(),
                        "sha256": file_sha256(image),
                    }
                    for image in image_files
                    if image.is_file()
                ],
            },
            _source_artifact_record(paper_root, "mineru/mineru-manifest.json"),
        ],
        "formula_review": {
            "status": "reviewed",
            "summary": (
                "Reviewed formulas from MinerU Markdown first; PDF, formula-index.json, "
                "figure-index.json, or image evidence were fallback checks only when ambiguous."
            ),
        },
        "figure_table_image_review": {
            "status": "reviewed",
            "summary": "Reviewed MinerU image assets and checked figure provenance.",
        },
        "pdf_fallback_review": {
            "status": "reviewed",
            "summary": "PDF fallback was available for source checks.",
        },
        "wiki_batch_ingest": {
            "status": "completed",
            "wiki_skill_used": EXPECTED_RESEARCH_WIKI_SKILLS,
            "optional_helpers_used": ["wiki-provenance", "tag-taxonomy"],
            "paper_slugs": [slug],
        },
        "theory_reconstruction": {
            "status": "reviewed",
            "summary": "Reconstructed the paper's theoretical assumptions and claim chain.",
        },
        "formula_derivation": {
            "status": "reviewed",
            "summary": "Reviewed derivation steps and noted any skipped algebra before wiki deposition.",
        },
        "figure_table_evidence": {
            "status": "reviewed",
            "summary": "Mapped key figures and tables to final-page evidence claims.",
        },
        "novelty_type": {
            "status": "reviewed",
            "summary": "Separated author-claimed novelty from Paper Source-confirmed novelty.",
        },
        "implementability": {
            "status": "reviewed",
            "summary": "Estimated implementation difficulty and required components.",
        },
        "reproducibility_risk": {
            "status": "reviewed",
            "summary": "Recorded dataset, code, compute, baseline, and metric risks.",
        },
        "research_gap": {
            "status": "reviewed",
            "summary": "Captured open problems that can become follow-up research directions.",
        },
        "cost_level": {
            "status": "reviewed",
            "summary": "Estimated resource cost level for implementation and validation.",
        },
        "page_lifecycle": {
            "status": "draft",
            "allowed_states": EXPECTED_PAGE_LIFECYCLE_STATES,
            "verified_requirements": [
                "source_reread",
                "formula_figure_review",
                "evidence_path_complete",
                "final_source_review_complete",
            ],
            "summary": "Agent-written final pages remain lifecycle=draft after source review.",
        },
        "formal_content_quality": {
            "status": "reviewed",
            "audit_pages_excluded": True,
            "language_policy": {
                "body_default_language": "zh",
                "chinese_body_default": True,
                "allowed_english": [
                    "paper titles",
                    "technical terms",
                    "abbreviations",
                    "evidence fields",
                    "paths",
                    "code",
                    "formulas",
                    "metrics",
                ],
            },
            "summary": "Final pages are readable wiki pages, not Paper Source audit or staging reports.",
        },
        "final_page_provenance": [
            {
                "relative_path": page.resolve().relative_to(vault.resolve()).as_posix(),
                "sha256": file_sha256(page),
                "source_grounded": True,
            }
            for page in pages
        ],
    }
    path = staging_root / "final-source-review.json"
    _write_json(path, payload)
    return path


def _approve_handoff(vault, slug, *, approved_by="codex-test"):
    return record_human_approval(
        vault,
        slug,
        approved_by=approved_by,
        scope="run-wiki-ingest-agent",
    )


def _write_paper_wiki_record_request(
    vault,
    slug,
    pages,
    source_review,
    *,
    approved_by="codex-test",
    page_hash_overrides=None,
):
    staging_root = vault / "_paper_source" / "staging" / "papers" / slug
    request_path = staging_root / "paper-wiki-record-request.json"
    final_pages = []
    overrides = page_hash_overrides or {}
    for page in pages:
        relative_path = page.relative_to(vault).as_posix()
        final_pages.append(
            {
                "relative_path": relative_path,
                "sha256": overrides.get(relative_path, file_sha256(page)),
            }
        )
    _write_json(
        request_path,
        {
            "schema_version": "paper-wiki-record-request-v1",
            "request_id": f"{slug}-fixture-request",
            "status": "ready_for_paper_source_record",
            "automation_mode": "ask",
            "paper_slug": slug,
            "final_pages": final_pages,
            "final_source_review": {
                "path": str(source_review),
                "sha256": file_sha256(source_review),
                "status": "verified",
            },
            "human_approval": {
                "approved_by": approved_by,
                "path": str(staging_root / "human-approval.json"),
            },
            "recommended_command": (
                "record-wiki-ingest "
                f"--from-paper-wiki-request _paper_source/staging/papers/{slug}/paper-wiki-record-request.json"
            ),
            "paper_wiki_task": {
                "plugin": "paper-research-wiki",
                "workflow": "extract-papers",
            },
        },
    )
    return request_path


def _enable_zotero(vault, *, collection="Paper Source Lab"):
    config = vault / "_paper_source" / "meta" / "paper-source-config.yaml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        "\n".join(
            [
                "profile: general_academic_research",
                "zotero:",
                "  enabled: true",
                f"  collection: {json.dumps(collection)}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _run_orchestrator_cli(monkeypatch, capsys, *args):
    monkeypatch.setattr(sys, "argv", ["paper_source.orchestrator", *args])
    exit_code = main()
    output = capsys.readouterr().out
    return exit_code, output


def test_record_wiki_ingest_records_agent_pages_without_modifying_them(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    reference = _write_final_page(
        vault,
        "references/fixture-paper.md",
        _formal_page_content("references", "Fixture Paper"),
    )
    concept = _write_final_page(
        vault,
        "concepts/navigation-control.md",
        _formal_page_content("concepts", "Navigation Control"),
    )
    source_review = _write_final_source_review(vault, slug, [reference, concept])
    _approve_handoff(vault, slug)
    before_hashes = {path: file_sha256(path) for path in [reference, concept]}

    result = record_wiki_ingest(
        vault,
        slug,
        [str(reference), "concepts/navigation-control.md"],
        approved_by="codex-test",
        notes="wiki agent applied target vault contract",
        source_review_path=str(source_review),
    )

    record = result["record"]
    assert record["status"] == "recorded"
    assert record["record_only"] is True
    assert record["compiled_wiki_write"] is False
    assert record["final_pages_modified_by_paper_source"] is False
    assert record["human_gate_decision"]["approved_by"] == "codex-test"
    assert record["source_first_confirmed"] is True
    assert record["source_first_verification_method"] == "final-source-review-json"
    assert record["final_source_review"]["status"] == "verified"
    assert record["paths"]["final_source_review"] == str(source_review)
    assert record["final_source_review"]["wiki_batch_ingest"]["wiki_skill_used"] == EXPECTED_RESEARCH_WIKI_SKILLS
    assert record["final_source_review"]["wiki_batch_ingest"].get("optional_helpers_used") == [
        "wiki-provenance",
        "tag-taxonomy",
    ]
    rule_sources = [item["source"] for item in record["wiki_rule_source_model"]["resolution_order"]]
    assert any("paper-research-wiki" in source for source in rule_sources)
    paper_wiki_index = next(index for index, source in enumerate(rule_sources) if "paper-research-wiki" in source)
    local_index = rule_sources.index("local llm-wiki / wiki-ingest / obsidian-markdown skills")
    assert paper_wiki_index < local_index
    for field in EXPECTED_RESEARCH_REVIEW_FIELDS:
        assert record["final_source_review"][field]["status"] == "reviewed"
    assert record["final_source_review"]["page_lifecycle"]["status"] == "draft"
    assert record["final_source_review"]["page_lifecycle"]["allowed_states"] == EXPECTED_PAGE_LIFECYCLE_STATES
    assert record["relative_page_paths"] == [
        "references/fixture-paper.md",
        "concepts/navigation-control.md",
    ]
    assert [item["sha256"] for item in record["page_records"]] == [
        before_hashes[reference],
        before_hashes[concept],
    ]
    assert file_sha256(reference) == before_hashes[reference]
    assert file_sha256(concept) == before_hashes[concept]

    raw_record = json.loads((vault / "_paper_source" / "raw" / slug / "wiki-ingest-record.json").read_text(encoding="utf-8"))
    staging_record = json.loads(
        (vault / "_paper_source" / "staging" / "papers" / slug / "wiki-ingest-record.json").read_text(encoding="utf-8")
    )
    assert raw_record["page_records"] == record["page_records"]
    assert staging_record["relative_page_paths"] == record["relative_page_paths"]

    gate = build_paper_gate(vault, slug)
    assert gate["status"] == "wiki_ingest_recorded"
    assert gate["next_action"] == "review-recorded-wiki-pages"
    checks = {run["name"]: run for run in gate["check_suite"]["check_runs"]}
    assert checks["human-approval"]["conclusion"] == "success"
    assert checks["human-approval"]["details"]["record_type"] == "wiki-ingest-record"

    run_dir = tmp_path / "vault" / "_paper_source" / "runs" / result["run_id"]
    report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    run_state = json.loads((run_dir / "run-state.json").read_text(encoding="utf-8"))
    paper_state = json.loads((vault / "_paper_source" / "raw" / slug / "run-state.json").read_text(encoding="utf-8"))
    assert report_json["workflow_type"] == "record-wiki-ingest"
    assert report_json["wiki_pages_written"] == ["references/fixture-paper.md", "concepts/navigation-control.md"]
    assert report_json["human_gate"]["status"] == "approved"
    assert report_json["page_records"][0]["relative_path"] == "references/fixture-paper.md"
    assert report_json["wiki_ingest_record"]["final_source_review"]["status"] == "verified"
    assert report_json["zotero_results"]["status"] == "skipped"
    assert report_json["zotero_results"]["reason"] == "zotero_not_configured"
    zotero_record = json.loads((vault / "_paper_source" / "raw" / slug / "zotero-record.json").read_text(encoding="utf-8"))
    assert zotero_record["wiki_ingest"]["final_wiki_pages"][0]["relative_path"] == "references/fixture-paper.md"
    assert run_state["compiled_wiki_write"] is False
    assert run_state["record_only"] is True
    assert run_state["input_artifact_hashes"]["final-source-review.json"] == file_sha256(source_review)
    assert run_state["zotero_results"]["reason"] == "zotero_not_configured"
    assert paper_state["state"] == "wiki_ingest_recorded"
    assert paper_state["next_action"] == "review-recorded-wiki-pages"


def test_record_wiki_ingest_replaces_paper_wiki_ready_corrected_premature_record(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    reference = _write_final_page(
        vault,
        "references/fixture-paper.md",
        _formal_page_content("references", "Fixture Paper"),
    )
    source_review = _write_final_source_review(vault, slug, [reference])
    _approve_handoff(vault, slug)
    paper_root = vault / "_paper_source" / "raw" / slug

    _write_json(
        paper_root / "wiki-ingest-record.json",
        {
            "schema_version": "paper-source-wiki-ingest-record-v1",
            "stage": "record-wiki-ingest",
            "status": "recorded",
            "paper_slug": slug,
            "recorded_at": "1999-01-01T00:00:00+00:00",
            "human_gate_decision": {"status": "approved", "approved_by": "codex-test"},
            "final_source_review": {
                "status": "verified",
                "path": str(source_review),
            },
            "page_records": [{"relative_path": "references/premature-fixture.md"}],
        },
    )
    _write_json(
        vault / "_paper_source" / "meta" / "record-corrections" / "20000101-premature.json",
        {
            "schema_version": "paper-source-record-correction-v1",
            "correction_type": "premature-wiki-ingest-record",
            "affected_papers": [
                {
                    "slug": slug,
                    "premature_record": f"_paper_source/raw/{slug}/wiki-ingest-record.json",
                }
            ],
            "status_after_correction": {
                "wiki_quality_status": "paper-wiki-reviewed-ready-for-paper-source-record",
                "record_status_interpretation": "Paper Wiki review complete; rerun record-wiki-ingest.",
            },
            "paper_wiki_repair": {
                "status": "completed",
                "completed_at": "2000-01-01T00:00:00+00:00",
                "final_source_reviews_refreshed": [str(source_review)],
            },
        },
    )

    pre_gate = build_paper_gate(vault, slug)
    pre_checks = {run["name"]: run for run in pre_gate["check_suite"]["check_runs"]}
    assert pre_gate["check_suite"]["conclusion"] == "success"
    assert pre_gate["next_action"] == "run-wiki-ingest-agent"
    assert pre_checks["record-correction"]["conclusion"] == "success"

    result = record_wiki_ingest(
        vault,
        slug,
        [str(reference)],
        approved_by="codex-test",
        source_review_path=str(source_review),
    )

    assert result["record"]["status"] == "recorded"
    after_gate = build_paper_gate(vault, slug)
    after_checks = {run["name"]: run for run in after_gate["check_suite"]["check_runs"]}
    assert after_gate["status"] == "wiki_ingest_recorded"
    assert after_gate["next_action"] == "review-recorded-wiki-pages"
    assert "record-correction" not in after_checks


def test_record_wiki_ingest_consumes_paper_wiki_record_request(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    reference = _write_final_page(
        vault,
        "references/fixture-paper.md",
        _formal_page_content("references", "Fixture Paper"),
    )
    source_review = _write_final_source_review(vault, slug, [reference])
    _approve_handoff(vault, slug)
    request_path = _write_paper_wiki_record_request(vault, slug, [reference], source_review)

    result = record_wiki_ingest(
        vault,
        None,
        [],
        approved_by=None,
        from_paper_wiki_request=str(request_path),
    )

    record = result["record"]
    assert record["status"] == "recorded"
    assert record["paper_slug"] == slug
    assert record["relative_page_paths"] == ["references/fixture-paper.md"]
    assert record["source_request"]["schema_version"] == "paper-wiki-record-request-v1"
    assert record["source_request"]["request_id"] == f"{slug}-fixture-request"
    assert record["source_request"]["automation_mode"] == "ask"
    assert record["source_request"]["path"] == str(request_path.resolve())
    assert record["source_request"]["sha256"] == file_sha256(request_path)
    assert record["human_gate_decision"]["approved_by"] == "codex-test"
    assert record["paths"]["final_source_review"] == str(source_review)
    raw_record = json.loads((vault / "_paper_source" / "raw" / slug / "wiki-ingest-record.json").read_text(encoding="utf-8"))
    assert raw_record["source_request"]["request_id"] == f"{slug}-fixture-request"
    run_state = json.loads((vault / "_paper_source" / "runs" / result["run_id"] / "run-state.json").read_text(encoding="utf-8"))
    assert run_state["input_artifact_hashes"]["paper-wiki-record-request.json"] == file_sha256(request_path)


def test_create_wiki_ingest_record_accepts_legacy_approval_and_source_review_schema_versions(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    page = _write_final_page(
        vault,
        "references/fixture-paper.md",
        _formal_page_content("references", "Fixture Paper"),
    )
    source_review = _write_final_source_review(vault, slug, [page])
    _approve_handoff(vault, slug)
    approval_path = vault / "_paper_source" / "staging" / "papers" / slug / "human-approval.json"
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    review = json.loads(source_review.read_text(encoding="utf-8"))
    approval["schema_version"] = "epi-human-approval-v1"
    review["schema_version"] = "epi-final-source-review-v1"
    _write_json(approval_path, approval)
    _write_json(source_review, review)

    record = create_wiki_ingest_record(
        vault,
        slug,
        [str(page)],
        approved_by="codex-test",
        source_review_path=str(source_review),
    )

    assert record["status"] == "recorded"
    assert record["final_source_review"]["schema_version"] == "epi-final-source-review-v1"


def test_record_wiki_ingest_from_paper_wiki_request_rejects_stale_page_hash(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    reference = _write_final_page(
        vault,
        "references/fixture-paper.md",
        _formal_page_content("references", "Fixture Paper"),
    )
    source_review = _write_final_source_review(vault, slug, [reference])
    _approve_handoff(vault, slug)
    request_path = _write_paper_wiki_record_request(
        vault,
        slug,
        [reference],
        source_review,
        page_hash_overrides={"references/fixture-paper.md": "stale-hash"},
    )

    with pytest.raises(ValueError, match="Paper Wiki record request final page sha256 mismatch"):
        record_wiki_ingest(
            vault,
            None,
            [],
            approved_by=None,
            from_paper_wiki_request=str(request_path),
        )

    assert not (vault / "_paper_source" / "raw" / slug / "wiki-ingest-record.json").exists()


def test_create_wiki_ingest_record_accepts_wiki_skill_batch_distillation_plan(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    plan_path = vault / "_paper_source" / "staging" / "papers" / slug / "promotion-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan.pop("handoff_type")
    plan["wiki_write_model"] = "wiki-skill-batch-distillation"
    _write_json(plan_path, plan)
    page = _write_final_page(
        vault,
        "references/fixture-paper.md",
        _formal_page_content("references", "Fixture Paper"),
    )
    source_review = _write_final_source_review(vault, slug, [page])
    _approve_handoff(vault, slug)

    record = create_wiki_ingest_record(
        vault,
        slug,
        [str(page)],
        approved_by="codex-test",
        source_review_path=str(source_review),
    )

    assert record["status"] == "recorded"
    assert record["wiki_write_model"] == "wiki-skill-batch-distillation"


def test_create_wiki_ingest_record_uses_paper_gate_source_bundle_audit_without_final_review(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    brief_path = vault / "_paper_source" / "staging" / "papers" / slug / "wiki-ingest-brief.json"
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["final_source_review_contract"]["required"] = False
    _write_json(brief_path, brief)
    page = _write_final_page(
        vault,
        "references/fixture-paper.md",
        _formal_page_content("references", "Fixture Paper"),
    )
    _approve_handoff(vault, slug)

    record = create_wiki_ingest_record(vault, slug, [str(page)], approved_by="codex-test")

    assert record["status"] == "recorded"
    assert record["source_first_confirmed"] is True
    assert record["source_first_verification_method"] == "paper-gate-source-bundle-audit"
    assert record["final_source_review"]["status"] == "missing"
    assert record["final_source_review"]["required"] is False
    assert record["paper_gate"]["source_bundle"]["status"] == "complete"


def test_record_wiki_ingest_validation_failure_does_not_create_empty_run_dir(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    page = _write_final_page(
        vault,
        "references/fixture-paper.md",
        _formal_page_content("references", "Fixture Paper"),
    )
    runs_dir = vault / "_paper_source" / "runs"
    before = sorted(path.name for path in runs_dir.glob("record-wiki-ingest-*")) if runs_dir.exists() else []

    with pytest.raises(ValueError, match="pre-write human approval"):
        record_wiki_ingest(vault, slug, [str(page)], approved_by="codex-test")

    after = sorted(path.name for path in runs_dir.glob("record-wiki-ingest-*")) if runs_dir.exists() else []
    assert after == before


def test_record_wiki_ingest_uses_enabled_zotero_config_in_report(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    _enable_zotero(vault, collection="Reading Lab")
    page = _write_final_page(
        vault,
        "references/fixture-paper.md",
        _formal_page_content("references", "Fixture Paper"),
    )
    source_review = _write_final_source_review(vault, slug, [page])
    _approve_handoff(vault, slug)

    result = record_wiki_ingest(
        vault,
        slug,
        [str(page)],
        approved_by="codex-test",
        source_review_path=str(source_review),
    )

    raw_zotero = json.loads((vault / "_paper_source" / "raw" / slug / "zotero-record.json").read_text(encoding="utf-8"))
    assert raw_zotero["schema_version"] == "paper-source-zotero-record-v1"
    assert raw_zotero["status"] == "recorded"
    assert raw_zotero["record_only"] is True
    assert raw_zotero["collection"] == "Reading Lab"
    assert raw_zotero["paper_metadata"]["title"] == "Fixture Paper"
    assert raw_zotero["wiki_ingest"]["status"] == "recorded"
    assert raw_zotero["wiki_ingest"]["final_wiki_pages"][0]["relative_path"] == "references/fixture-paper.md"

    run_dir = vault / "_paper_source" / "runs" / result["run_id"]
    report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    report_md = (run_dir / "report.md").read_text(encoding="utf-8")
    assert report_json["zotero_results"]["status"] == "recorded"
    assert report_json["zotero_results"]["collection"] == "Reading Lab"
    assert "## Zotero" in report_md
    assert "- status: recorded" in report_md
    assert "- final_wiki_pages: 1" in report_md


def test_create_wiki_ingest_record_rejects_missing_human_approval(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    page = _write_final_page(
        vault,
        "references/fixture-paper.md",
        _formal_page_content("references", "Fixture Paper"),
    )

    with pytest.raises(ValueError, match="human gate approval"):
        create_wiki_ingest_record(vault, slug, [str(page)], approved_by="")

    assert not (vault / "_paper_source" / "raw" / slug / "wiki-ingest-record.json").exists()


def test_create_wiki_ingest_record_rejects_missing_prewrite_approval_artifact(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    page = _write_final_page(
        vault,
        "references/fixture-paper.md",
        _formal_page_content("references", "Fixture Paper"),
    )

    with pytest.raises(ValueError, match="pre-write human approval"):
        create_wiki_ingest_record(vault, slug, [str(page)], approved_by="codex-test")

    assert not (vault / "_paper_source" / "raw" / slug / "wiki-ingest-record.json").exists()


def test_create_wiki_ingest_record_rejects_mismatched_prewrite_approval_actor(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    page = _write_final_page(
        vault,
        "references/fixture-paper.md",
        _formal_page_content("references", "Fixture Paper"),
    )
    source_review = _write_final_source_review(vault, slug, [page])
    _approve_handoff(vault, slug, approved_by="codex-test")

    with pytest.raises(ValueError, match="does not match pre-write human approval"):
        create_wiki_ingest_record(
            vault,
            slug,
            [str(page)],
            approved_by="different-reviewer",
            source_review_path=str(source_review),
        )


def test_create_wiki_ingest_record_rejects_pages_outside_vault(tmp_path):
    vault = tmp_path / "vault"
    outside = tmp_path / "outside.md"
    outside.write_text("# Outside\n", encoding="utf-8")
    slug = _seed_agent_handoff(vault)
    _approve_handoff(vault, slug)

    with pytest.raises(ValueError, match="inside vault"):
        create_wiki_ingest_record(vault, slug, [str(outside)], approved_by="codex-test")


def test_create_wiki_ingest_record_rejects_internal_staging_page_as_final_page(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    staging_page = vault / "_paper_source" / "staging" / "papers" / slug / "evidence" / "source-reader.md"
    _approve_handoff(vault, slug)

    with pytest.raises(ValueError, match="must not be under _paper_source"):
        create_wiki_ingest_record(vault, slug, [str(staging_page)], approved_by="codex-test")


def test_create_wiki_ingest_record_rejects_missing_formal_frontmatter(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    page = _write_final_page(
        vault,
        "references/missing-frontmatter.md",
        "# Missing Frontmatter\n\nThis links to [[concepts/fixture-method-family]] but lacks required properties.\n",
    )
    source_review = _write_final_source_review(vault, slug, [page])
    _approve_handoff(vault, slug)

    with pytest.raises(ValueError, match="frontmatter"):
        create_wiki_ingest_record(
            vault,
            slug,
            [str(page)],
            approved_by="codex-test",
            source_review_path=str(source_review),
        )


def test_create_wiki_ingest_record_accepts_obsidian_uri_pdf_source(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    page = _write_final_page(
        vault,
        "references/fixture-paper.md",
        _formal_page_content("references", "Fixture Paper"),
    )
    source_review = _write_final_source_review(vault, slug, [page])
    _approve_handoff(vault, slug)

    record = create_wiki_ingest_record(
        vault,
        slug,
        [str(page)],
        approved_by="codex-test",
        source_review_path=str(source_review),
    )

    assert record["status"] == "recorded"
    assert record["relative_page_paths"] == ["references/fixture-paper.md"]


def test_create_wiki_ingest_record_accepts_nested_provenance_yaml_lists(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    page = _write_final_page(
        vault,
        "references/nested-provenance.md",
        _formal_page_content("references", "Nested Provenance").replace(
            '  extracted: ["mineru/fixture-paper.md#method"]\n'
            "  inferred: []\n"
            "  ambiguous: []\n",
            "  extracted:\n"
            "    - mineru/fixture-paper.md#method\n"
            "  inferred:\n"
            "    - comparison with [[concepts/fixture-method-family]]\n"
            "  ambiguous:\n"
            "    - table label requires PDF fallback\n",
        ),
    )
    source_review = _write_final_source_review(vault, slug, [page])
    _approve_handoff(vault, slug)

    record = create_wiki_ingest_record(
        vault,
        slug,
        [str(page)],
        approved_by="codex-test",
        source_review_path=str(source_review),
    )

    assert record["status"] == "recorded"
    assert record["relative_page_paths"] == ["references/nested-provenance.md"]


def test_create_wiki_ingest_record_rejects_legacy_review_needed_lifecycle_state(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    page = _write_final_page(
        vault,
        "references/review-needed-lifecycle.md",
        _formal_page_content("references", "Review Needed Lifecycle").replace(
            "lifecycle: draft",
            "lifecycle: review-needed",
        ),
    )
    source_review = _write_final_source_review(vault, slug, [page])
    payload = json.loads(source_review.read_text(encoding="utf-8"))
    payload["page_lifecycle"]["status"] = "review-needed"
    payload["page_lifecycle"]["summary"] = "Final pages are source reviewed but still need human graph review."
    _write_json(source_review, payload)
    _approve_handoff(vault, slug)

    with pytest.raises(ValueError, match="lifecycle is not allowed|page_lifecycle"):
        create_wiki_ingest_record(
            vault,
            slug,
            [str(page)],
            approved_by="codex-test",
            source_review_path=str(source_review),
        )


def test_create_wiki_ingest_record_rejects_plain_pdf_path_in_frontmatter_sources(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    page = _write_final_page(
        vault,
        "references/plain-text-source.md",
        _formal_page_content("references", "Plain Text Source").replace(
            f'sources: ["{_obsidian_uri_pdf_source(title="Plain Text Source")}"]',
            'sources: ["_paper_source/raw/fixture-paper/paper.pdf (原论文 PDF)"]',
        ),
    )
    source_review = _write_final_source_review(vault, slug, [page])
    _approve_handoff(vault, slug)

    with pytest.raises(ValueError, match="Markdown links to canonical source PDFs"):
        create_wiki_ingest_record(
            vault,
            slug,
            [str(page)],
            approved_by="codex-test",
            source_review_path=str(source_review),
        )


def test_create_wiki_ingest_record_rejects_legacy_epi_body_pdf_link(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    page = _write_final_page(
        vault,
        "references/legacy-epi-body-link.md",
        _formal_page_content("references", "Legacy EPI Body Link").replace(
            _obsidian_uri_pdf_url(),
            _legacy_obsidian_uri_pdf_url(),
        ),
    )
    source_review = _write_final_source_review(vault, slug, [page])
    _approve_handoff(vault, slug)

    with pytest.raises(ValueError, match="canonical _paper_source/raw/<slug>/paper.pdf|legacy _epi/raw"):
        create_wiki_ingest_record(
            vault,
            slug,
            [str(page)],
            approved_by="codex-test",
            source_review_path=str(source_review),
        )


def test_create_wiki_ingest_record_accepts_markdown_pdf_link_in_frontmatter_sources(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    page = _write_final_page(
        vault,
        "references/markdown-source-link.md",
        _formal_page_content("references", "Markdown Source Link").replace(
            f'sources: ["{_obsidian_uri_pdf_source(title="Markdown Source Link")}"]',
            'sources: ["[Markdown Source Link](obsidian://open?vault=paper-research-wiki&file=_paper_source%2Fraw%2Ffixture-paper%2Fpaper.pdf)"]',
        ),
    )
    source_review = _write_final_source_review(vault, slug, [page])
    _approve_handoff(vault, slug)

    record = create_wiki_ingest_record(
        vault,
        slug,
        [str(page)],
        approved_by="codex-test",
        source_review_path=str(source_review),
    )
    assert record["status"] == "recorded"


def test_create_wiki_ingest_record_rejects_relative_markdown_pdf_link_in_frontmatter_sources(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    page = _write_final_page(
        vault,
        "references/relative-markdown-source-link.md",
        _formal_page_content("references", "Relative Markdown Source Link").replace(
            f'sources: ["{_obsidian_uri_pdf_source(title="Relative Markdown Source Link")}"]',
            'sources: ["[Relative Markdown Source Link](_paper_source/raw/fixture-paper/paper.pdf)"]',
        ),
    )
    source_review = _write_final_source_review(vault, slug, [page])
    _approve_handoff(vault, slug)

    with pytest.raises(ValueError, match="Markdown links to canonical source PDFs"):
        create_wiki_ingest_record(
            vault,
            slug,
            [str(page)],
            approved_by="codex-test",
            source_review_path=str(source_review),
        )


def test_create_wiki_ingest_record_rejects_internal_pdf_wikilink_source(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    page = _write_final_page(
        vault,
        "references/internal-pdf-wikilink-source.md",
        _formal_page_content("references", "Source Alias Not Slug").replace(
            f'sources: ["{_obsidian_uri_pdf_source(title="Source Alias Not Slug")}"]',
            'sources: ["[[_paper_source/raw/fixture-paper/paper.pdf|fixture-paper 原论文 PDF]]"',
        ),
    )
    source_review = _write_final_source_review(vault, slug, [page])
    _approve_handoff(vault, slug)

    with pytest.raises(ValueError, match="not internal wikilinks|not internal"):
        create_wiki_ingest_record(
            vault,
            slug,
            [str(page)],
            approved_by="codex-test",
            source_review_path=str(source_review),
        )


@pytest.mark.parametrize(
    "extra_source",
    [
        '"[[_paper_source/raw/fixture-paper/metadata.json|metadata.json]]"',
        '"[[_paper_source/raw/fixture-paper/mineru/fixture-paper.md|MinerU Markdown]]"',
        '"https://doi.org/10.1000/fixture"',
    ],
)
def test_create_wiki_ingest_record_rejects_non_label_entries_in_frontmatter_sources(tmp_path, extra_source):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    page = _write_final_page(
        vault,
        "references/non-pdf-source-entry.md",
        _formal_page_content("references", "Non PDF Source Entry").replace(
            f'sources: ["{_obsidian_uri_pdf_source(title="Non PDF Source Entry")}"]',
            f'sources: ["{_obsidian_uri_pdf_source(title="Non PDF Source Entry")}", '
            + extra_source
            + "]",
        ),
    )
    source_review = _write_final_source_review(vault, slug, [page])
    _approve_handoff(vault, slug)

    with pytest.raises(ValueError, match="canonical source PDFs|body provenance|not internal wikilinks"):
        create_wiki_ingest_record(
            vault,
            slug,
            [str(page)],
            approved_by="codex-test",
            source_review_path=str(source_review),
        )


def test_create_wiki_ingest_record_rejects_fenced_formula_blocks(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    page = _write_final_page(
        vault,
        "derivations/fixture-derivation.md",
        _formal_page_content(
            "derivations",
            "Fixture Derivation",
            body=(
                "# Fixture Derivation\n\n"
                "This derivation links to [[concepts/fixture-method-family]].\n\n"
                "## Variable Definitions\n\n"
                "- x: input\n- y: output\n\n"
                "## Derivation Chain\n\n"
                "```math\n"
                "y = x + 1\n"
                "```\n"
            ),
        ),
    )
    source_review = _write_final_source_review(vault, slug, [page])
    _approve_handoff(vault, slug)

    with pytest.raises(ValueError, match="fenced formula"):
        create_wiki_ingest_record(
            vault,
            slug,
            [str(page)],
            approved_by="codex-test",
            source_review_path=str(source_review),
        )


def test_create_wiki_ingest_record_rejects_audit_shaped_final_page(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    page = _write_final_page(
        vault,
        "concepts/fixture-audit.md",
        _formal_page_content(
            "concepts",
            "Fixture Audit",
            body="# Audit\n\n## Wiki Ingest Brief\n\n- Evidence claims tracked: 3\n- reader/claim-support.json\n",
        ),
    )
    source_review = _write_final_source_review(vault, slug, [page])
    _approve_handoff(vault, slug)

    with pytest.raises(ValueError, match="audit/staging artifact"):
        create_wiki_ingest_record(
            vault,
            slug,
            [str(page)],
            approved_by="codex-test",
            source_review_path=str(source_review),
        )


def test_create_wiki_ingest_record_rejects_english_only_formal_page_body(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    page = _write_final_page(
        vault,
        "references/english-only.md",
        _formal_page_content(
            "references",
            "English Only Fixture",
            body=(
                "# English Only Fixture\n\n"
                "This page links source-backed claims to [[concepts/fixture-method-family]] and preserves evidence routes.\n\n"
                "## Model And Method\n\n"
                "The page records the method, assumptions, and control variables from the source bundle.\n\n"
                "## Key Formulas\n\n"
                "$$y = x + 1$$\n\n"
                "## Experiments And Metrics\n\n"
                "The experiment section records baselines, metrics, and evaluation settings.\n\n"
                "## Limitations\n\n"
                "Limitations and caveats remain tied to the source artifacts.\n"
            ),
        ),
    )
    source_review = _write_final_source_review(vault, slug, [page])
    _approve_handoff(vault, slug)

    with pytest.raises(ValueError, match="Chinese-default"):
        create_wiki_ingest_record(
            vault,
            slug,
            [str(page)],
            approved_by="codex-test",
            source_review_path=str(source_review),
        )


def test_create_wiki_ingest_record_requires_final_source_review_language_policy(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    page = _write_final_page(
        vault,
        "references/chinese-fixture.md",
        _formal_page_content(
            "references",
            "Chinese Fixture",
            body=(
                "# 中文正文夹具\n\n"
                "这页用中文正文记录 [[concepts/fixture-method-family]] 的来源证据和方法边界。\n\n"
                "## 模型与方法\n\n"
                "方法部分保留 model 和 method 等英文术语，但解释默认使用中文。\n\n"
                "## 公式\n\n"
                "$$y = x + 1$$\n\n"
                "## 实验与指标\n\n"
                "实验部分记录 baseline、metric 和评估设置。\n\n"
                "## 局限\n\n"
                "局限和 caveat 需要绑定到来源证据。\n"
            ),
        ),
    )
    source_review = _write_final_source_review(vault, slug, [page])
    _approve_handoff(vault, slug)

    payload = json.loads(source_review.read_text(encoding="utf-8"))
    payload["formal_content_quality"].pop("language_policy", None)
    _write_json(source_review, payload)

    with pytest.raises(ValueError, match="language_policy"):
        create_wiki_ingest_record(
            vault,
            slug,
            [str(page)],
            approved_by="codex-test",
            source_review_path=str(source_review),
        )


def test_create_wiki_ingest_record_rejects_per_paper_pseudo_routes(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    page = _write_final_page(
        vault,
        "concepts/fixture-paper-concept.md",
        _formal_page_content("concepts", "Fixture Paper Concept"),
    )
    source_review = _write_final_source_review(vault, slug, [page])
    _approve_handoff(vault, slug)

    with pytest.raises(ValueError, match="per-paper routes"):
        create_wiki_ingest_record(
            vault,
            slug,
            [str(page)],
            approved_by="codex-test",
            source_review_path=str(source_review),
        )


def test_create_wiki_ingest_record_rejects_missing_required_final_source_review_artifact(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    page = _write_final_page(
        vault,
        "references/fixture-paper.md",
        _formal_page_content("references", "Fixture Paper"),
    )
    source_review = _write_final_source_review(vault, slug, [page])
    _approve_handoff(vault, slug)
    payload = json.loads(source_review.read_text(encoding="utf-8"))
    payload["reviewed_artifacts"] = [
        item for item in payload["reviewed_artifacts"] if item["artifact"] != "mineru/fixture-paper.md"
    ]
    _write_json(source_review, payload)

    with pytest.raises(ValueError, match="final source review.*mineru/fixture-paper.md"):
        create_wiki_ingest_record(
            vault,
            slug,
            [str(page)],
            approved_by="codex-test",
            source_review_path=str(source_review),
        )


def test_create_wiki_ingest_record_requires_research_review_contract(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    page = _write_final_page(
        vault,
        "references/fixture-paper.md",
        _formal_page_content("references", "Fixture Paper"),
    )
    source_review = _write_final_source_review(vault, slug, [page])
    _approve_handoff(vault, slug)
    payload = json.loads(source_review.read_text(encoding="utf-8"))
    payload["wiki_batch_ingest"]["wiki_skill_used"] = ["epi-wiki-deposition", "wiki-ingest", "wiki-provenance"]
    payload.pop("formula_derivation")
    payload["page_lifecycle"]["status"] = "not-a-real-state"
    _write_json(source_review, payload)

    with pytest.raises(ValueError, match="paper-research-wiki.*formula_derivation.*page_lifecycle"):
        create_wiki_ingest_record(
            vault,
            slug,
            [str(page)],
            approved_by="codex-test",
            source_review_path=str(source_review),
        )


def test_create_wiki_ingest_record_rejects_non_list_optional_helpers(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    page = _write_final_page(
        vault,
        "references/fixture-paper.md",
        _formal_page_content("references", "Fixture Paper"),
    )
    source_review = _write_final_source_review(vault, slug, [page])
    _approve_handoff(vault, slug)
    payload = json.loads(source_review.read_text(encoding="utf-8"))
    payload["wiki_batch_ingest"]["optional_helpers_used"] = "wiki-provenance"
    _write_json(source_review, payload)

    with pytest.raises(ValueError, match="optional_helpers_used must be a list"):
        create_wiki_ingest_record(
            vault,
            slug,
            [str(page)],
            approved_by="codex-test",
            source_review_path=str(source_review),
        )


def test_record_wiki_ingest_cli_outputs_json(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    page = _write_final_page(
        vault,
        "references/fixture-paper.md",
        _formal_page_content("references", "Fixture Paper"),
    )
    source_review = _write_final_source_review(vault, slug, [page])
    _approve_handoff(vault, slug)

    exit_code, output = _run_orchestrator_cli(
        monkeypatch,
        capsys,
        "record-wiki-ingest",
        "--vault",
        str(vault),
        "--slug",
        slug,
        "--page",
        str(page),
        "--approved-by",
        "codex-test",
        "--source-review",
        str(source_review),
        "--json",
    )

    payload = json.loads(output)
    assert exit_code == 0
    assert payload["record"]["status"] == "recorded"
    assert payload["record"]["relative_page_paths"] == ["references/fixture-paper.md"]
    assert payload["record"]["source_first_verification_method"] == "final-source-review-json"
    assert payload["run_id"].startswith("record-wiki-ingest-")
    assert payload["zotero_results"]["status"] == "skipped"
    assert payload["zotero_record_path"].endswith("zotero-record.json")
