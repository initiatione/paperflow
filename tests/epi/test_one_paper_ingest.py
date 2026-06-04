import json

import pytest

from epi.orchestrator import run_one_paper_ingest
from epi.run_critic import run_critics
from epi.stage_wiki import stage_paper


EXPECTED_RESEARCH_WIKI_SKILLS = [
    "paper-research-wiki",
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


def _write_phase2_fixture(tmp_path):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4\nfixture paper\n")
    mineru_md = tmp_path / "paper.md"
    mineru_md.write_text(
        "# Abstract\n\nThis paper presents embodied navigation control for mobile robots.\n\n"
        "# Method\n\nThe controller combines perception, planning, and feedback control.\n",
        encoding="utf-8",
    )
    mineru_tex = tmp_path / "paper.tex"
    mineru_tex.write_text("\\section{Abstract} Fixture paper.\n", encoding="utf-8")
    candidate = {
        "id": "doi:10.1000/nav",
        "slug": "embodied-navigation-control-for-mobile-robots",
        "title": "Embodied Navigation Control for Mobile Robots",
        "authors": ["B. Engineer"],
        "year": 2024,
        "venue": "IROS",
        "abstract": "Robotics navigation and control with code.",
        "doi": "10.1000/nav",
        "pdf_url": "file://fixture-paper.pdf",
        "citation_count": 9,
        "score": 0.82,
        "sources": ["fixture"],
    }
    return candidate, pdf, mineru_md, mineru_tex


def test_one_paper_ingest_preserves_raw_artifacts_and_stages_after_critic_pass(tmp_path):
    candidate, pdf, mineru_md, mineru_tex = _write_phase2_fixture(tmp_path)

    result = run_one_paper_ingest(
        vault_path=tmp_path / "vault",
        candidate=candidate,
        pdf_path=pdf,
        mineru_markdown_path=mineru_md,
        mineru_tex_path=mineru_tex,
        workflow_mode="audited-ingest",
    )

    paper_root = result["paper_root"]
    staging_root = result["staging_root"]
    slug = candidate["slug"]
    canonical_mineru_md = f"mineru/{slug}.md"

    assert (paper_root / "paper.pdf").read_bytes() == pdf.read_bytes()
    assert (paper_root / "metadata.json").is_file()
    assert (paper_root / "acquire-record.json").is_file()
    assert (paper_root / "mineru" / f"{slug}.md").is_file()
    assert not (paper_root / "mineru" / "paper.md").exists()
    assert (paper_root / "mineru" / "paper.tex").is_file()
    assert (paper_root / "reader" / "reader.md").read_text(encoding="utf-8").count("Evidence:") >= 2
    assert (paper_root / "reader" / "evidence-map.json").is_file()
    assert (paper_root / "reader" / "claim-support.json").is_file()
    assert (paper_root / "critic" / "paper-quality-critic.md").is_file()
    assert (paper_root / "critic" / "parse-quality-critic.md").is_file()
    assert (paper_root / "critic" / "reader-quality-critic.md").is_file()
    assert (paper_root / "critic" / "editorial-significance-critic.md").is_file()
    assert (paper_root / "critic" / "peer-review-methods-critic.md").is_file()
    assert (paper_root / "critic" / "domain-fit-critic.md").is_file()
    assert (paper_root / "critic" / "critic-quorum.json").is_file()

    reader_record = result["run_manifest"]["reader_record"]
    parse_record = result["run_manifest"]["parse_record"]
    assert result["run_manifest"]["workflow_mode"] == "audited-ingest"
    assert parse_record["started_at"]
    assert parse_record["finished_at"]
    assert parse_record["exit_status"] == 0
    assert parse_record["input_artifact_hashes"]["fixture_markdown"]
    assert parse_record["output_artifact_hashes"][f"{slug}.md"]
    assert "paper.md" not in parse_record["output_artifact_hashes"]
    assert parse_record["output_artifact_hashes"]["paper.tex"]
    assert reader_record["started_at"]
    assert reader_record["finished_at"]
    assert reader_record["exit_status"] == 0
    assert reader_record["input_artifact_hashes"]["metadata.json"]
    assert reader_record["input_artifact_hashes"][canonical_mineru_md]
    assert reader_record["output_artifact_hashes"]["reader.md"]
    assert reader_record["output_artifact_hashes"]["editorial-summary.md"]
    assert reader_record["output_artifact_hashes"]["technical-reading.md"]
    assert reader_record["output_artifact_hashes"]["research-notes.md"]
    assert reader_record["output_artifact_hashes"]["figures.md"]
    assert reader_record["output_artifact_hashes"]["reproducibility.md"]
    assert reader_record["output_artifact_hashes"]["implementation-ideas.md"]
    assert reader_record["output_artifact_hashes"]["evidence-map.json"]
    assert reader_record["output_artifact_hashes"]["claim-support.json"]

    critic = json.loads((paper_root / "critic" / "critic-report.json").read_text(encoding="utf-8"))
    assert critic["outcome"] == "pass"
    assert critic["hard_rule"] == "No critic pass, no compiled wiki write."
    assert critic["reviewer_quorum_path"] == str(paper_root / "critic" / "critic-quorum.json")
    assert critic["reviewer_count"] == 6
    assert critic["disagreement"] is False

    quorum = json.loads((paper_root / "critic" / "critic-quorum.json").read_text(encoding="utf-8"))
    assert quorum["stage"] == "critic-quorum"
    assert quorum["final_outcome"] == "pass"
    assert quorum["disagreement"] is False
    assert [reviewer["name"] for reviewer in quorum["reviewers"]] == [
        "paper-quality-critic",
        "parse-quality-critic",
        "reader-quality-critic",
        "editorial-significance-critic",
        "peer-review-methods-critic",
        "domain-fit-critic",
    ]
    for reviewer in quorum["reviewers"]:
        assert reviewer["mode"] == "local"
        assert reviewer["verdict"] == "pass"
        assert reviewer["scope"]
        assert reviewer["evidence"]

    assert not (staging_root / "references" / f"{slug}.md").exists()
    assert not (staging_root / "concepts" / f"{slug}-concept.md").exists()
    assert not (staging_root / "synthesis" / f"{slug}-synthesis.md").exists()
    source_reader_path = staging_root / "evidence" / "source-reader.md"
    reading_report_path = staging_root / "briefs" / "reading-report.md"
    assert source_reader_path.is_file()
    assert reading_report_path.is_file()
    assert "formal_page: false" in source_reader_path.read_text(encoding="utf-8")
    reading_report_text = reading_report_path.read_text(encoding="utf-8")
    assert "page_type: reading_report" in reading_report_text
    assert "formal_page: false" in reading_report_text
    assert "# Embodied Navigation Control for Mobile Robots 阅读报告" in reading_report_text
    assert "## 快速判断" in reading_report_text
    assert "## 论文身份" in reading_report_text
    assert "## 术语中英对照" in reading_report_text
    assert "移动机器人（Mobile Robot）" in reading_report_text
    assert "控制（Control）" in reading_report_text
    assert "## 理论与方法" in reading_report_text
    assert "## 实验/验证方式" in reading_report_text
    assert "## 证据强度与可信状态" in reading_report_text
    assert "- 可信状态：accepted-with-caveats" in reading_report_text
    assert "- 警告审稿器：paper-quality-critic" in reading_report_text
    assert "## Wiki 沉淀价值" in reading_report_text
    assert "- EPI 只写 `_epi/` 内部材料；正式图谱页由 wiki skill 批量沉淀生成。" in reading_report_text
    assert "## 沉淀建议" in reading_report_text
    assert any(marker in reading_report_text for marker in ["建议沉淀", "谨慎沉淀", "暂不沉淀"])
    assert "## Quick Take" not in reading_report_text
    assert "## Wiki Skill Handoff" not in reading_report_text
    assert "Inference:" not in reading_report_text
    assert "A UTONOMOUS" not in reading_report_text
    assert reading_report_text.index("## 理论与方法") < reading_report_text.index(
        "## 主要 Caveat"
    )
    assert "## Reproduction Plans" not in reading_report_text
    wiki_ingest_brief_path = staging_root / "wiki-ingest-brief.json"
    assert wiki_ingest_brief_path.is_file()
    wiki_ingest_brief = json.loads(wiki_ingest_brief_path.read_text(encoding="utf-8"))
    assert wiki_ingest_brief["schema_version"] == "epi-wiki-ingest-brief-v1"
    assert wiki_ingest_brief["handoff_type"] == "agent-mediated-wiki-ingest"
    assert wiki_ingest_brief["paper_slug"] == slug
    assert wiki_ingest_brief["trust_status"]["status"] == "accepted-with-caveats"
    assert "wiki skill batch distillation" in wiki_ingest_brief["ingest_policy"]["final_page_authority"]
    assert wiki_ingest_brief["ingest_policy"]["epi_write_scope"] == "internal-underscore-artifacts-only"
    assert wiki_ingest_brief["ingest_policy"]["formal_routes_suggested"] is False
    assert wiki_ingest_brief["ingest_policy"]["wiki_batch_handoff_required"] is True
    assert wiki_ingest_brief["ingest_policy"]["required_wiki_skills"] == EXPECTED_RESEARCH_WIKI_SKILLS
    assert wiki_ingest_brief["formal_page_families"] == EXPECTED_FORMAL_PAGE_FAMILIES
    assert wiki_ingest_brief["research_review_fields"] == EXPECTED_RESEARCH_REVIEW_FIELDS
    assert wiki_ingest_brief["page_lifecycle_states"] == EXPECTED_PAGE_LIFECYCLE_STATES
    assert "target vault contract" in wiki_ingest_brief["ingest_policy"]["authority"]
    assert "Markdown vault" in wiki_ingest_brief["ingest_policy"]["source_of_truth"]
    assert canonical_mineru_md in wiki_ingest_brief["ingest_policy"]["source_first_policy"]
    assert "not substitutes for the source paper" in wiki_ingest_brief["ingest_policy"]["source_first_policy"]
    assert "target vault AGENTS.md" in wiki_ingest_brief["vault_contract_resolution"]
    assert "_meta/schema.md" in wiki_ingest_brief["vault_contract_resolution"]
    framework_names = [item["name"] for item in wiki_ingest_brief["wiki_framework_references"]]
    assert "Ar9av/obsidian-wiki" in framework_names
    assert "kepano/obsidian-skills" in framework_names
    assert "initiatione/obsidian-wiki-dev" in framework_names
    final_source_review_contract = wiki_ingest_brief["final_source_review_contract"]
    assert final_source_review_contract["schema_version"] == "epi-final-source-review-contract-v1"
    assert final_source_review_contract["required"] is True
    assert final_source_review_contract["suggested_output_path"] == "final-source-review.json"
    assert final_source_review_contract["record_schema_version"] == "epi-final-source-review-v1"
    assert "mineru/paper.tex" in final_source_review_contract["required_artifacts"]
    assert final_source_review_contract["required_wiki_skills"] == EXPECTED_RESEARCH_WIKI_SKILLS
    assert final_source_review_contract["formal_page_families"] == EXPECTED_FORMAL_PAGE_FAMILIES
    assert final_source_review_contract["research_review_fields"] == EXPECTED_RESEARCH_REVIEW_FIELDS
    assert final_source_review_contract["page_lifecycle_states"] == EXPECTED_PAGE_LIFECYCLE_STATES
    must_record = "\n".join(final_source_review_contract["must_record"])
    for field in EXPECTED_RESEARCH_REVIEW_FIELDS:
        assert field in must_record
    assert "verified" in must_record
    execution_agent_policy = wiki_ingest_brief["wiki_rule_source_model"]["execution_agent_policy"]
    assert execution_agent_policy["allowed_executors"][:2] == ["Claude", "Codex"]
    assert "target vault contract" in execution_agent_policy["brand_neutrality"]
    rule_sources = [
        item["source"]
        for item in wiki_ingest_brief["wiki_rule_source_model"]["resolution_order"]
    ]
    assert rule_sources[0] == "current user instruction"
    assert "target vault AGENTS.md" in rule_sources
    assert any("_meta/schema.md" in source for source in rule_sources)
    assert any("liuchf/wiki-skills" in source for source in rule_sources)
    assert any("paper-research-wiki" in source for source in rule_sources)
    assert "local llm-wiki / wiki-ingest / obsidian-markdown skills" in rule_sources
    prw_index = next(index for index, source in enumerate(rule_sources) if "paper-research-wiki" in source)
    local_index = rule_sources.index("local llm-wiki / wiki-ingest / obsidian-markdown skills")
    assert prw_index < local_index
    prw_role = next(
        item["role"]
        for item in wiki_ingest_brief["wiki_rule_source_model"]["resolution_order"]
        if "paper-research-wiki" in item["source"]
    )
    assert "canonical" in prw_role
    assert "compatibility adapter" in prw_role
    local_skill_role = next(
        item["role"]
        for item in wiki_ingest_brief["wiki_rule_source_model"]["resolution_order"]
        if item["source"] == "local llm-wiki / wiki-ingest / obsidian-markdown skills"
    )
    assert "do not replace the target vault contract" in local_skill_role
    assert any(
        "Markdown vault files as the source of truth" in requirement
        for requirement in wiki_ingest_brief["wiki_rule_source_model"]["write_contract_requirements"]
    )
    assert "Claude" in wiki_ingest_brief["ingest_policy"]["executor_policy"]
    assert "Codex" in wiki_ingest_brief["ingest_policy"]["executor_policy"]
    assert wiki_ingest_brief["entrypoints"]["reading_report"] == "briefs/reading-report.md"
    assert wiki_ingest_brief["entrypoints"]["source_reader"] == "evidence/source-reader.md"
    assert wiki_ingest_brief["formal_routes_suggested"] is False
    assert wiki_ingest_brief["suggested_routes"] == []
    assert [target["artifact_type"] for target in wiki_ingest_brief["handoff_artifacts"]] == [
        "source_reader",
        "reading_report",
        "optional_reader_aids",
        "optional_critic_aids",
    ]
    assert {target["route_status"] for target in wiki_ingest_brief["handoff_artifacts"]} == {
        "internal-evidence-only"
    }
    assert wiki_ingest_brief["wiki_skill_handoff"]["batch_required"] is True
    assert wiki_ingest_brief["wiki_skill_handoff"]["required_skills"] == EXPECTED_RESEARCH_WIKI_SKILLS
    minimum_role = wiki_ingest_brief["wiki_skill_handoff"]["minimum_role"]
    for skill in EXPECTED_RESEARCH_WIKI_SKILLS:
        assert skill in minimum_role
    assert "load paper-research-wiki first" in minimum_role
    assert "epi-paper-deposition" in minimum_role
    assert "compatibility adapter" in minimum_role
    assert "load epi-paper-deposition, llm-wiki" not in minimum_role
    assert wiki_ingest_brief["wiki_skill_handoff"]["formal_page_families"] == EXPECTED_FORMAL_PAGE_FAMILIES
    assert wiki_ingest_brief["source_bundle"]["raw_artifacts"] == [
        "paper.pdf",
        "metadata.json",
        canonical_mineru_md,
        "mineru/paper.tex",
        "mineru/images/*",
        "mineru/mineru-manifest.json",
    ]
    optional_aids = wiki_ingest_brief["source_bundle"]["optional_evidence_aids"]
    assert "reader/evidence-map.json" in optional_aids
    assert "reader/claim-support.json" in optional_aids
    assert "reader/figures.md" in optional_aids
    assert "critic/critic-report.json" in optional_aids
    assert "critic/research-decision.json" in optional_aids
    assert wiki_ingest_brief["source_bundle"]["primary_source_reading_order"][:5] == [
        "metadata.json",
        canonical_mineru_md,
        "mineru/paper.tex",
        "mineru/images/*",
        "mineru/mineru-manifest.json",
    ]
    formula_figure_review = wiki_ingest_brief["source_bundle"]["formula_figure_review"]
    assert "central formulas" in formula_figure_review["formulas"]
    assert "figures/tables/images" in formula_figure_review["figures_tables_images"]
    assert "paper.pdf" in formula_figure_review["parse_uncertainty"]
    assert wiki_ingest_brief["source_bundle"]["evidence"]["claim_count"] >= 3
    assert wiki_ingest_brief["source_bundle"]["evidence"]["claim_support_artifact"] == "reader/claim-support.json"
    assert wiki_ingest_brief["source_bundle"]["evidence"]["reader_roles"] == [
        "nature-sci-editor",
        "peer-reviewer",
        "senior-domain-researcher",
    ]
    promotion_plan = json.loads((staging_root / "promotion-plan.json").read_text(encoding="utf-8"))
    assert promotion_plan["workflow_mode"] == "audited-ingest"
    assert promotion_plan["reader_required"] is True
    assert promotion_plan["critic_required"] is True
    assert promotion_plan["critic_outcome"] == "pass"
    assert promotion_plan["handoff_type"] == "agent-mediated-wiki-ingest"
    assert promotion_plan["wiki_write_model"] == "wiki-skill-batch-distillation"
    assert promotion_plan["final_page_authority"] == "wiki-skill-batch-distillation"
    assert promotion_plan["epi_write_scope"] == "internal-underscore-artifacts-only"
    assert promotion_plan["formal_routes_suggested"] is False
    assert promotion_plan["wiki_batch_handoff_required"] is True
    assert promotion_plan["required_wiki_skills"] == EXPECTED_RESEARCH_WIKI_SKILLS
    assert promotion_plan["formal_page_families"] == EXPECTED_FORMAL_PAGE_FAMILIES
    assert promotion_plan["research_review_fields"] == EXPECTED_RESEARCH_REVIEW_FIELDS
    assert promotion_plan["page_lifecycle_states"] == EXPECTED_PAGE_LIFECYCLE_STATES
    assert promotion_plan["wiki_ingest_brief_path"] == str(wiki_ingest_brief_path)
    batch_handoff_path = tmp_path / "vault" / "_epi" / "staging" / "wiki-batches" / "pending" / "wiki-batch-ingest-brief.json"
    assert promotion_plan["wiki_batch_ingest_brief_path"] == str(batch_handoff_path)
    assert batch_handoff_path.is_file()
    batch_handoff = json.loads(batch_handoff_path.read_text(encoding="utf-8"))
    assert batch_handoff["schema_version"] == "epi-wiki-batch-ingest-brief-v1"
    assert slug in batch_handoff["paper_slugs"]
    assert batch_handoff["epi_write_scope"] == "internal-underscore-artifacts-only"
    assert batch_handoff["formal_routes_suggested"] is False
    assert batch_handoff["required_wiki_skills"] == EXPECTED_RESEARCH_WIKI_SKILLS
    for skill in EXPECTED_RESEARCH_WIKI_SKILLS:
        assert skill in batch_handoff["wiki_skill_instruction"]
    assert "Load paper-research-wiki first" in batch_handoff["wiki_skill_instruction"]
    assert "epi-paper-deposition" in batch_handoff["wiki_skill_instruction"]
    assert "compatibility adapter" in batch_handoff["wiki_skill_instruction"]
    assert "Load epi-paper-deposition," not in batch_handoff["wiki_skill_instruction"]
    assert batch_handoff["formal_page_families"] == EXPECTED_FORMAL_PAGE_FAMILIES
    assert batch_handoff["research_review_fields"] == EXPECTED_RESEARCH_REVIEW_FIELDS
    assert batch_handoff["page_lifecycle_states"] == EXPECTED_PAGE_LIFECYCLE_STATES
    assert promotion_plan["suggested_final_source_review_path"] == str(staging_root / "final-source-review.json")
    assert promotion_plan["final_source_review_contract"]["required"] is True
    assert str(reading_report_path) in promotion_plan["agent_handoff_paths"]
    assert str(wiki_ingest_brief_path) in promotion_plan["agent_handoff_paths"]
    assert "compiled_targets" not in promotion_plan
    assert promotion_plan["research_decision_path"] == str(paper_root / "critic" / "research-decision.json")
    assert promotion_plan["reproduction_plan_path"] == str(paper_root / "critic" / "reproduction-plan.json")
    assert promotion_plan["panel_summary"]["consensus"] == "approve-for-staging"
    assert [item["lens"] for item in promotion_plan["role_assessments"]] == [
        "nature-sci-editor",
        "peer-reviewer",
        "senior-domain-researcher",
    ]
    assert all(item["action"] == "preserve" for item in promotion_plan["role_assessments"])
    assert "staged_reference" not in promotion_plan
    assert "staged_concepts" not in promotion_plan
    assert "staged_synthesis" not in promotion_plan
    assert promotion_plan["staged_evidence"] == [str(source_reader_path)]
    assert promotion_plan["staged_reports"] == [str(reading_report_path)]
    assert promotion_plan["suggested_route_targets"] == []
    source_reader = source_reader_path.read_text(encoding="utf-8")
    assert 'epi_recommendation: "stage-for-promotion-review"' in source_reader
    assert 'epi_panel_consensus: "approve-for-staging"' in source_reader
    assert 'epi_nature_sci_editor_verdict: "pass"' in source_reader
    assert 'epi_peer_reviewer_verdict: "pass"' in source_reader
    assert 'epi_senior_domain_researcher_verdict: "pass"' in source_reader
    assert "epi_blocking_lenses: []" in source_reader
    assert "epi_warning_reviewers:" in source_reader
    assert "## Research Decision" in source_reader
    assert "Consensus: approve-for-staging" in source_reader
    assert "nature-sci-editor: pass -> preserve" in source_reader
    assert "peer-reviewer: pass -> preserve" in source_reader
    assert "senior-domain-researcher: pass -> preserve" in source_reader
    assert "## Promotion Review Inputs" in source_reader
    assert not (tmp_path / "vault" / "references" / f"{slug}.md").exists()


def test_stage_paper_rejects_nonpassing_critic(tmp_path):
    paper_root = tmp_path / "_epi" / "raw" / "papers" / "paper"
    critic_dir = paper_root / "critic"
    reader_dir = paper_root / "reader"
    critic_dir.mkdir(parents=True)
    reader_dir.mkdir(parents=True)
    (reader_dir / "reader.md").write_text("# Reader\n", encoding="utf-8")
    (critic_dir / "critic-report.json").write_text(
        json.dumps({"outcome": "revise-reader", "hard_rule": "No critic pass, no compiled wiki write."}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="critic outcome"):
        stage_paper(tmp_path, "paper", paper_root)

    assert not (tmp_path / "_epi" / "staging" / "papers" / "paper").exists()


def test_critic_quorum_records_reviewer_failure_without_staging(tmp_path):
    vault = tmp_path / "vault"
    slug = "critic-failure-paper"
    paper_root = vault / "_epi" / "raw" / "papers" / slug
    (paper_root / "mineru").mkdir(parents=True)
    (paper_root / "reader").mkdir(parents=True)
    (paper_root / "paper.pdf").write_bytes(b"%PDF-1.4\n")
    (paper_root / "metadata.json").write_text(
        json.dumps({"slug": slug, "title": "Fixture Paper", "doi": "10.1000/fixture", "venue": "IROS"}),
        encoding="utf-8",
    )
    (paper_root / "mineru" / f"{slug}.md").write_text("# Paper\n\nParsed content.\n", encoding="utf-8")
    (paper_root / "reader" / "reader.md").write_text("# Reader\n\nUnsupported claim.\n", encoding="utf-8")

    critic = run_critics(paper_root)

    assert critic["outcome"] == "revise-reader"
    assert critic["next_action"] == "revise-reader"
    assert critic["reviewer_count"] == 6
    assert critic["disagreement"] is True
    quorum = json.loads((paper_root / "critic" / "critic-quorum.json").read_text(encoding="utf-8"))
    assert quorum["final_outcome"] == "revise-reader"
    assert quorum["disagreement"] is True
    assert [reviewer["verdict"] for reviewer in quorum["reviewers"]] == [
        "pass",
        "pass",
        "fail",
        "fail",
        "fail",
        "fail",
    ]

    with pytest.raises(ValueError, match="critic outcome"):
        stage_paper(vault, slug, paper_root)

    assert not (vault / "_epi" / "staging" / "papers" / slug).exists()


def test_critic_quorum_records_missing_reader_as_reviewer_failure(tmp_path):
    slug = "missing-reader-paper"
    paper_root = tmp_path / "_epi" / "raw" / "papers" / slug
    (paper_root / "mineru").mkdir(parents=True)
    (paper_root / "paper.pdf").write_bytes(b"%PDF-1.4\n")
    (paper_root / "metadata.json").write_text(
        json.dumps({"slug": slug, "title": "Fixture Paper", "doi": "10.1000/fixture", "venue": "IROS"}),
        encoding="utf-8",
    )
    (paper_root / "mineru" / f"{slug}.md").write_text("# Paper\n\nParsed content.\n", encoding="utf-8")

    critic = run_critics(paper_root)

    assert critic["outcome"] == "revise-reader"
    assert critic["disagreement"] is True
    quorum = json.loads((paper_root / "critic" / "critic-quorum.json").read_text(encoding="utf-8"))
    reader_reviewer = quorum["reviewers"][2]
    assert reader_reviewer["name"] == "reader-quality-critic"
    assert reader_reviewer["verdict"] == "fail"
    assert "reader/reader.md missing" in reader_reviewer["evidence"]
