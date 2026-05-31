import json

import pytest

from epi.orchestrator import run_one_paper_ingest
from epi.run_critic import run_critics
from epi.stage_wiki import stage_paper


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
    )

    paper_root = result["paper_root"]
    staging_root = result["staging_root"]
    slug = candidate["slug"]

    assert (paper_root / "paper.pdf").read_bytes() == pdf.read_bytes()
    assert (paper_root / "metadata.json").is_file()
    assert (paper_root / "acquire-record.json").is_file()
    assert (paper_root / "mineru" / "paper.md").is_file()
    assert (paper_root / "mineru" / "paper.tex").is_file()
    assert (paper_root / "reader" / "reader.md").read_text(encoding="utf-8").count("Evidence:") >= 2
    assert (paper_root / "reader" / "evidence-map.json").is_file()
    assert (paper_root / "critic" / "paper-quality-critic.md").is_file()
    assert (paper_root / "critic" / "parse-quality-critic.md").is_file()
    assert (paper_root / "critic" / "reader-quality-critic.md").is_file()
    assert (paper_root / "critic" / "editorial-significance-critic.md").is_file()
    assert (paper_root / "critic" / "peer-review-methods-critic.md").is_file()
    assert (paper_root / "critic" / "domain-fit-critic.md").is_file()
    assert (paper_root / "critic" / "critic-quorum.json").is_file()

    reader_record = result["run_manifest"]["reader_record"]
    parse_record = result["run_manifest"]["parse_record"]
    assert parse_record["started_at"]
    assert parse_record["finished_at"]
    assert parse_record["exit_status"] == 0
    assert parse_record["input_artifact_hashes"]["fixture_markdown"]
    assert parse_record["output_artifact_hashes"]["paper.md"]
    assert parse_record["output_artifact_hashes"]["paper.tex"]
    assert reader_record["started_at"]
    assert reader_record["finished_at"]
    assert reader_record["exit_status"] == 0
    assert reader_record["input_artifact_hashes"]["metadata.json"]
    assert reader_record["input_artifact_hashes"]["mineru/paper.md"]
    assert reader_record["output_artifact_hashes"]["reader.md"]
    assert reader_record["output_artifact_hashes"]["editorial-summary.md"]
    assert reader_record["output_artifact_hashes"]["technical-reading.md"]
    assert reader_record["output_artifact_hashes"]["research-notes.md"]
    assert reader_record["output_artifact_hashes"]["figures.md"]
    assert reader_record["output_artifact_hashes"]["reproducibility.md"]
    assert reader_record["output_artifact_hashes"]["implementation-ideas.md"]
    assert reader_record["output_artifact_hashes"]["evidence-map.json"]

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

    assert (staging_root / "references" / f"{slug}.md").is_file()
    concept_path = staging_root / "concepts" / f"{slug}-concept.md"
    synthesis_path = staging_root / "synthesis" / f"{slug}-synthesis.md"
    reading_report_path = staging_root / "reports" / f"{slug}-reading-report.md"
    assert concept_path.is_file()
    assert synthesis_path.is_file()
    assert reading_report_path.is_file()
    assert f"reference_page: references/{slug}.md" in concept_path.read_text(encoding="utf-8")
    assert f"reference_page: references/{slug}.md" in synthesis_path.read_text(encoding="utf-8")
    reading_report_text = reading_report_path.read_text(encoding="utf-8")
    assert "page_type: reading_report" in reading_report_text
    assert "## Quick Take" in reading_report_text
    assert "## Reading Trust Status" in reading_report_text
    assert "- Status: accepted-with-caveats" in reading_report_text
    assert "- Warning reviewers: paper-quality-critic" in reading_report_text
    assert "Read `Quick Take`, `Reading Trust Status`, `Quality Gates`, and `Suggested Wiki Routes` first." in reading_report_text
    assert "## What To Read If You Only Have 5 Minutes" in reading_report_text
    assert "## Wiki Ingest Brief" in reading_report_text
    assert "- Ingest brief: `wiki-ingest-brief.json`" in reading_report_text
    assert "- Trust status: accepted-with-caveats" in reading_report_text
    assert "- Final wiki pages: created by the wiki-ingest agent, not fixed by EPI staging." in reading_report_text
    assert "## Theory And Experiment Ideas" in reading_report_text
    assert "## Evidence Map" in reading_report_text
    assert "## Suggested Wiki Routes" in reading_report_text
    assert "## Quality Gates" in reading_report_text
    assert "## Reproducibility Caveats" in reading_report_text
    assert reading_report_text.index("## Theory And Experiment Ideas") < reading_report_text.index(
        "## Reproducibility Caveats"
    )
    assert "## Reproduction Plans" not in reading_report_text
    wiki_ingest_brief_path = staging_root / "wiki-ingest-brief.json"
    assert wiki_ingest_brief_path.is_file()
    wiki_ingest_brief = json.loads(wiki_ingest_brief_path.read_text(encoding="utf-8"))
    assert wiki_ingest_brief["schema_version"] == "epi-wiki-ingest-brief-v1"
    assert wiki_ingest_brief["handoff_type"] == "agent-mediated-wiki-ingest"
    assert wiki_ingest_brief["paper_slug"] == slug
    assert wiki_ingest_brief["trust_status"]["status"] == "accepted-with-caveats"
    assert "not fixed by EPI staging" in wiki_ingest_brief["ingest_policy"]["final_page_authority"]
    assert wiki_ingest_brief["ingest_policy"]["suggested_routes_only"] is True
    assert "target vault contract" in wiki_ingest_brief["ingest_policy"]["authority"]
    assert "Markdown vault" in wiki_ingest_brief["ingest_policy"]["source_of_truth"]
    assert "mineru/paper.md" in wiki_ingest_brief["ingest_policy"]["source_first_policy"]
    assert "not substitutes for the source paper" in wiki_ingest_brief["ingest_policy"]["source_first_policy"]
    assert "target vault AGENTS.md" in wiki_ingest_brief["vault_contract_resolution"]
    assert "_meta/schema.md" in wiki_ingest_brief["vault_contract_resolution"]
    framework_names = [item["name"] for item in wiki_ingest_brief["wiki_framework_references"]]
    assert "Ar9av/obsidian-wiki" in framework_names
    assert "kepano/obsidian-skills" in framework_names
    assert "initiatione/obsidian-wiki-dev" in framework_names
    rule_sources = [
        item["source"]
        for item in wiki_ingest_brief["wiki_rule_source_model"]["resolution_order"]
    ]
    assert rule_sources[0] == "current user instruction"
    assert "target vault AGENTS.md" in rule_sources
    assert any("_meta/schema.md" in source for source in rule_sources)
    assert any("liuchf/wiki-skills" in source for source in rule_sources)
    assert "local llm-wiki / wiki-ingest / obsidian-markdown skills" in rule_sources
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
    assert wiki_ingest_brief["entrypoints"]["reading_report"] == f"reports/{slug}-reading-report.md"
    assert [target["page_type"] for target in wiki_ingest_brief["suggested_routes"]] == [
        "reference",
        "concept",
        "synthesis",
        "reading_report",
    ]
    assert {target["route_status"] for target in wiki_ingest_brief["suggested_routes"]} == {"suggested-by-epi"}
    assert wiki_ingest_brief["source_bundle"]["raw_artifacts"] == [
        "paper.pdf",
        "metadata.json",
        "mineru/paper.md",
        "mineru/paper.tex",
        "mineru/images/*",
        "mineru/mineru-manifest.json",
    ]
    assert wiki_ingest_brief["source_bundle"]["primary_source_reading_order"][:5] == [
        "metadata.json",
        "mineru/paper.md",
        "mineru/paper.tex",
        "mineru/images/*",
        "mineru/mineru-manifest.json",
    ]
    formula_figure_review = wiki_ingest_brief["source_bundle"]["formula_figure_review"]
    assert "central formulas" in formula_figure_review["formulas"]
    assert "figures/tables/images" in formula_figure_review["figures_tables_images"]
    assert "paper.pdf" in formula_figure_review["parse_uncertainty"]
    assert wiki_ingest_brief["source_bundle"]["evidence"]["claim_count"] >= 3
    assert wiki_ingest_brief["source_bundle"]["evidence"]["reader_roles"] == [
        "nature-sci-editor",
        "peer-reviewer",
        "senior-domain-researcher",
    ]
    promotion_plan = json.loads((staging_root / "promotion-plan.json").read_text(encoding="utf-8"))
    assert promotion_plan["critic_outcome"] == "pass"
    assert promotion_plan["handoff_type"] == "agent-mediated-wiki-ingest"
    assert promotion_plan["wiki_write_model"] == "agent-mediated-vault-contract"
    assert promotion_plan["final_page_authority"] == "target-vault-contract-and-wiki-ingest-agent"
    assert promotion_plan["wiki_ingest_brief_path"] == str(wiki_ingest_brief_path)
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
    assert promotion_plan["staged_reference"] == str(staging_root / "references" / f"{slug}.md")
    assert promotion_plan["staged_concepts"] == [str(concept_path)]
    assert promotion_plan["staged_synthesis"] == [str(synthesis_path)]
    assert promotion_plan["staged_reports"] == [str(reading_report_path)]
    assert promotion_plan["suggested_route_targets"] == [
        f"references/{slug}.md",
        f"concepts/{slug}-concept.md",
        f"synthesis/{slug}-synthesis.md",
        f"reports/{slug}-reading-report.md",
    ]
    staged_reference = (staging_root / "references" / f"{slug}.md").read_text(encoding="utf-8")
    assert 'epi_recommendation: "stage-for-promotion-review"' in staged_reference
    assert 'epi_panel_consensus: "approve-for-staging"' in staged_reference
    assert 'epi_nature_sci_editor_verdict: "pass"' in staged_reference
    assert 'epi_peer_reviewer_verdict: "pass"' in staged_reference
    assert 'epi_senior_domain_researcher_verdict: "pass"' in staged_reference
    assert "epi_blocking_lenses: []" in staged_reference
    assert "epi_warning_reviewers:" in staged_reference
    assert "## Research Decision" in staged_reference
    assert "Consensus: approve-for-staging" in staged_reference
    assert "nature-sci-editor: pass -> preserve" in staged_reference
    assert "peer-reviewer: pass -> preserve" in staged_reference
    assert "senior-domain-researcher: pass -> preserve" in staged_reference
    assert "## Promotion Review Inputs" in concept_path.read_text(encoding="utf-8")
    assert "## Promotion Review Inputs" in synthesis_path.read_text(encoding="utf-8")
    assert not (tmp_path / "vault" / "references" / f"{slug}.md").exists()


def test_stage_paper_rejects_nonpassing_critic(tmp_path):
    paper_root = tmp_path / "_raw" / "papers" / "paper"
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

    assert not (tmp_path / "_staging" / "papers" / "paper").exists()


def test_critic_quorum_records_reviewer_failure_without_staging(tmp_path):
    vault = tmp_path / "vault"
    slug = "paper"
    paper_root = vault / "_raw" / "papers" / slug
    (paper_root / "mineru").mkdir(parents=True)
    (paper_root / "reader").mkdir(parents=True)
    (paper_root / "paper.pdf").write_bytes(b"%PDF-1.4\n")
    (paper_root / "metadata.json").write_text(
        json.dumps({"slug": slug, "title": "Fixture Paper", "doi": "10.1000/fixture", "venue": "IROS"}),
        encoding="utf-8",
    )
    (paper_root / "mineru" / "paper.md").write_text("# Paper\n\nParsed content.\n", encoding="utf-8")
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

    assert not (vault / "_staging" / "papers" / slug).exists()


def test_critic_quorum_records_missing_reader_as_reviewer_failure(tmp_path):
    slug = "paper"
    paper_root = tmp_path / "_raw" / "papers" / slug
    (paper_root / "mineru").mkdir(parents=True)
    (paper_root / "paper.pdf").write_bytes(b"%PDF-1.4\n")
    (paper_root / "metadata.json").write_text(
        json.dumps({"slug": slug, "title": "Fixture Paper", "doi": "10.1000/fixture", "venue": "IROS"}),
        encoding="utf-8",
    )
    (paper_root / "mineru" / "paper.md").write_text("# Paper\n\nParsed content.\n", encoding="utf-8")

    critic = run_critics(paper_root)

    assert critic["outcome"] == "revise-reader"
    assert critic["disagreement"] is True
    quorum = json.loads((paper_root / "critic" / "critic-quorum.json").read_text(encoding="utf-8"))
    reader_reviewer = quorum["reviewers"][2]
    assert reader_reviewer["name"] == "reader-quality-critic"
    assert reader_reviewer["verdict"] == "fail"
    assert "reader/reader.md missing" in reader_reviewer["evidence"]
