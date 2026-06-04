import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "PRW"
PUBLIC_SKILL = PLUGIN / "skills" / "paper-research-wiki"
MARKETPLACES = [
    ROOT / "marketplace.json",
    ROOT / ".agents" / "plugins" / "marketplace.json",
]
WORKFLOWS = {
    "extract-papers.md",
    "check-wiki.md",
    "update-wiki.md",
    "redo-extraction.md",
}
PUBLIC_SKILLS = {"paper-research-wiki"}
SUPPORT_SKILLS = {"paper-wiki-language"}
REFERENCES = {
    "epi-artifact-contract.md",
    "page-provenance.md",
    "page-family-contract.md",
    "upstream-obsidian-wiki-map.md",
}
FORMAL_PAGE_FAMILIES = {
    "references/",
    "concepts/",
    "derivations/",
    "experiments/",
    "synthesis/",
    "reports/",
    "opportunities/",
}
FORBIDDEN_FORMAL_ROOTS = {
    "_epi/",
    "_raw/",
    "_staging/",
    "_runs/",
    "_quarantine/",
    ".obsidian/",
}


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_plugin_manifest_exposes_simple_user_prompts():
    manifest = _read_json(PLUGIN / ".codex-plugin" / "plugin.json")

    assert manifest["name"] == "prw"
    assert manifest["version"] == "0.1.1"
    assert manifest["skills"] == "./skills/"
    assert manifest["interface"]["displayName"] == "Paper Research Wiki"
    assert "academic paper knowledge" in manifest["description"]
    assert "link repair" in manifest["interface"]["longDescription"]
    assert "QMD-compatible" in manifest["interface"]["longDescription"]
    assert "post-task check" in manifest["interface"]["longDescription"]
    prompt_text = "\n".join(manifest["interface"]["defaultPrompt"])
    for phrase in ["提取", "检测", "更新", "沉淀", "EPI", "link", "QMD"]:
        assert phrase in prompt_text


def test_marketplaces_register_paper_research_wiki():
    for marketplace_path in MARKETPLACES:
        marketplace = _read_json(marketplace_path)
        entries = {entry["name"]: entry for entry in marketplace["plugins"]}

        assert "prw" in entries, marketplace_path
        entry = entries["prw"]
        assert entry["source"] == {
            "source": "local",
            "path": "./plugins/PRW",
        }
        assert entry["policy"] == {
            "installation": "AVAILABLE",
            "authentication": "ON_INSTALL",
        }
        assert entry["category"] == "Productivity"


def test_plugin_has_one_public_skill_plus_language_gate():
    skill_dirs = {
        path.name
        for path in (PLUGIN / "skills").iterdir()
        if path.is_dir() and (path / "SKILL.md").exists()
    }
    assert skill_dirs == PUBLIC_SKILLS | SUPPORT_SKILLS
    language_skill = _read(PLUGIN / "skills" / "paper-wiki-language" / "SKILL.md")
    assert "formal PRW/EPI" in language_skill
    assert "Language Gate" in language_skill


def test_public_skill_routes_natural_epi_deposition_actions():
    skill = _read(PUBLIC_SKILL / "SKILL.md")

    for phrase in [
        "提取",
        "检测",
        "更新",
        "沉淀",
        "直接沉淀",
        "继续上次",
        "默认",
        "重link",
        "重做",
        "重新提取",
        "更详细",
        "批量",
        "relink",
        "redo",
        "extract",
        "check",
        "update",
    ]:
        assert phrase in skill
    for workflow in WORKFLOWS:
        assert f"workflows/{workflow}" in skill
        path = PUBLIC_SKILL / "workflows" / workflow
        assert path.exists(), workflow
        assert path.read_text(encoding="utf-8").strip(), workflow


def test_public_skill_references_internal_contract_files():
    skill = _read(PUBLIC_SKILL / "SKILL.md")

    for reference in REFERENCES:
        assert f"references/{reference}" in skill
        path = PUBLIC_SKILL / "references" / reference
        assert path.exists(), reference
        assert path.read_text(encoding="utf-8").strip(), reference


def test_public_skill_defaults_epi_wiki_requests_to_deposition():
    skill = _read(PUBLIC_SKILL / "SKILL.md")

    for phrase in [
        "EPI",
        "ready",
        "preflight",
        "沉淀",
        "wiki_deposition_task.json",
        "workflows/extract-papers.md",
        "workflows/check-wiki.md",
    ]:
        assert phrase in skill


def test_required_docs_and_rules_exist():
    required = [
        "AGENTS.md",
        "docs/workflow.md",
        "docs/structure.md",
        "docs/epi-integration.md",
        "docs/provenance.md",
        "docs/privacy.md",
        "docs/terms.md",
        "rules/source-trust.md",
        "rules/page-families.md",
        "rules/formal-page-frontmatter.md",
        "rules/wiki-writing-standard.md",
    ]

    for relative in required:
        path = PLUGIN / relative
        assert path.exists(), relative
        assert path.read_text(encoding="utf-8").strip(), relative


def test_page_family_rules_capture_formal_and_forbidden_roots():
    text = _read(PLUGIN / "rules" / "page-families.md")

    for family in FORMAL_PAGE_FAMILIES:
        assert family in text
    for root in FORBIDDEN_FORMAL_ROOTS:
        assert root in text


def test_epi_integration_docs_name_handoff_and_record_contracts():
    text = _read(PLUGIN / "docs" / "epi-integration.md")

    for phrase in [
        "wiki_deposition_task.json",
        "wiki-ingest-brief.json",
        "final-source-review.json",
        "record-wiki-ingest",
        "paper-gate",
        "human approval",
    ]:
        assert phrase in text


def test_provenance_docs_preserve_claim_support_statuses():
    text = _read(PLUGIN / "docs" / "provenance.md")

    for phrase in [
        "source-grounded",
        "metadata-only",
        "inferred",
        "unsupported",
        "evidence address",
        "formula",
        "figure",
    ]:
        assert phrase in text


def test_upstream_obsidian_wiki_map_covers_core_skill_families():
    text = _read(PUBLIC_SKILL / "references" / "upstream-obsidian-wiki-map.md")

    for phrase in [
        "Ar9av/obsidian-wiki",
        "wiki-ingest",
        "wiki-update",
        "wiki-status",
        "cross-linker",
        "tag-taxonomy",
        "wiki-lint",
    ]:
        assert phrase in text


def test_upstream_obsidian_wiki_map_is_internalized_not_runtime_fetch():
    text = _read(PUBLIC_SKILL / "references" / "upstream-obsidian-wiki-map.md")

    for phrase in [
        "design source, not a runtime source of truth",
        "do not fetch or search Ar9av/obsidian-wiki",
        "normal PRW runs",
        "local PRW workflows",
        "upstream repository only when maintaining PRW",
    ]:
        assert phrase in text


def test_prw_internalizes_link_repair_qmd_and_post_task_checks():
    skill = _read(PUBLIC_SKILL / "SKILL.md")
    standard = _read(PLUGIN / "rules" / "wiki-writing-standard.md")
    upstream = _read(PUBLIC_SKILL / "references" / "upstream-obsidian-wiki-map.md")
    check = _read(PUBLIC_SKILL / "workflows" / "check-wiki.md")
    update = _read(PUBLIC_SKILL / "workflows" / "update-wiki.md")
    extract = _read(PUBLIC_SKILL / "workflows" / "extract-papers.md")
    redo = _read(PUBLIC_SKILL / "workflows" / "redo-extraction.md")
    workflow_doc = _read(PLUGIN / "docs" / "workflow.md")

    for text in [skill, standard, upstream, check, update, extract, redo, workflow_doc]:
        assert "post-task check" in text

    for text in [check, update, upstream, workflow_doc]:
        for phrase in [
            "broken wikilinks",
            "ambiguous aliases",
            "duplicate concept owners",
            "forbidden internal links",
            "relationship direction",
        ]:
            assert phrase in text

    for text in [check, update, extract, redo, upstream, workflow_doc]:
        for phrase in [
            "QMD",
            "qmd update",
            "qmd embed",
            "fallback to manifest",
            "block on qmd query",
        ]:
            assert phrase.lower() in text.lower()

    for text in [extract, redo, update]:
        assert "Run `workflows/check-wiki.md` after writing" in text


def test_prw_declares_closed_loop_boundary_and_completion_definition():
    skill = _read(PUBLIC_SKILL / "SKILL.md")
    standard = _read(PLUGIN / "rules" / "wiki-writing-standard.md")
    workflow_doc = _read(PLUGIN / "docs" / "workflow.md")
    epi_integration = _read(PLUGIN / "docs" / "epi-integration.md")

    for text in [skill, workflow_doc]:
        assert "Check -> Diagnose -> Plan -> Act -> Verify -> Refresh -> Record -> Next" in text

    for text in [skill, standard, workflow_doc]:
        assert (
            "A PRW task is not complete until formal pages, tracking files, graph links, "
            "taxonomy, provenance, language gate, QMD freshness, and EPI record readiness "
            "have been checked or explicitly reported as skipped with reason."
        ) in text

    for text in [skill, workflow_doc, epi_integration]:
        for phrase in [
            "PRW owns",
            "EPI owns",
            "paper discovery",
            "MinerU parsing",
            "paper-gate",
            "human approval",
            "record-wiki-ingest",
            "final-source-review.json",
        ]:
            assert phrase in text


def test_check_wiki_supports_layered_checks_and_completion_reports():
    check = _read(PUBLIC_SKILL / "workflows" / "check-wiki.md")
    workflow_doc = _read(PLUGIN / "docs" / "workflow.md")

    for text in [check, workflow_doc]:
        for phrase in [
            "Quick check",
            "Targeted check",
            "Full check",
            "Quick + Targeted",
            "systemic link/tag chaos",
        ]:
            assert phrase in text

    for phrase in [
        "Completion Report",
        "pages created or updated",
        "links/tags/aliases repaired",
        "tracking files updated",
        "QMD refreshed / skipped / failed with fallback",
        "remaining risks",
        "next EPI/PRW action",
    ]:
        assert phrase in check


def test_update_wiki_has_controlled_link_repair_mechanism():
    update = _read(PUBLIC_SKILL / "workflows" / "update-wiki.md")

    for phrase in [
        "Scan formal pages",
        "canonical page map",
        "alias map",
        "broken wikilinks",
        "orphan pages",
        "duplicate pages",
        "relationship drift",
        "repair plan",
        "small batches",
        "staging patch",
        "rerun the post-task check",
    ]:
        assert phrase in update


def test_workflows_adapt_upstream_ingest_status_update_and_relink_patterns():
    extract = _read(PUBLIC_SKILL / "workflows" / "extract-papers.md")
    check = _read(PUBLIC_SKILL / "workflows" / "check-wiki.md")
    update = _read(PUBLIC_SKILL / "workflows" / "update-wiki.md")
    provenance = _read(PUBLIC_SKILL / "references" / "page-provenance.md")

    for phrase in [
        "distill and integrate",
        "existing related pages",
        "manifest",
        "index.md",
        "log.md",
        "hot.md",
        "relationships:",
    ]:
        assert phrase in extract

    for phrase in [
        "What to Do Next",
        "pending EPI handoffs",
        "orphan",
        "broken wikilinks",
        "staged writes",
        "provenance gaps",
    ]:
        assert phrase in check

    for phrase in [
        "cross-linker",
        "tag-taxonomy",
        "wiki-lint",
        "missing wikilinks",
        "aliases",
        "one confirmation",
    ]:
        assert phrase in update

    for phrase in ["relationships:", "source-grounded", "unsupported"]:
        assert phrase in provenance


def test_prw_enforces_ar9av_style_wiki_writing_standard():
    standard_path = PLUGIN / "rules" / "wiki-writing-standard.md"
    standard = _read(standard_path)
    skill = _read(PUBLIC_SKILL / "SKILL.md")
    extract = _read(PUBLIC_SKILL / "workflows" / "extract-papers.md")
    check = _read(PUBLIC_SKILL / "workflows" / "check-wiki.md")
    update = _read(PUBLIC_SKILL / "workflows" / "update-wiki.md")

    assert "../../rules/wiki-writing-standard.md" in skill
    for text in [extract, check, update]:
        assert "../../../rules/wiki-writing-standard.md" in text

    for phrase in [
        "Do not summarize papers in isolation",
        "merge before create",
        "page template",
        "frontmatter",
        "title:",
        "category:",
        "page_family:",
        "tags:",
        "aliases:",
        "relationships:",
        "sources:",
        "summary:",
        "provenance:",
        "base_confidence:",
        "lifecycle:",
        "lifecycle_changed:",
        "tier:",
        "created:",
        "updated:",
        "Key Ideas",
        "Open Questions",
        "Sources",
        "manifest",
        "index.md",
        "log.md",
        "hot.md",
        "orphan",
        "broken wikilinks",
        "relationship issues",
        "staged writes",
        "final-source-review.json",
        "record-wiki-ingest",
    ]:
        assert phrase in standard


def test_prw_supports_single_and_batch_redo_deep_extraction():
    skill = _read(PUBLIC_SKILL / "SKILL.md")
    redo = _read(PUBLIC_SKILL / "workflows" / "redo-extraction.md")
    metadata = _read(PUBLIC_SKILL / "agents" / "openai.yaml")

    assert "workflows/redo-extraction.md" in skill
    for phrase in ["重做", "重新提取", "更详细", "批量", "redo", "deep extraction"]:
        assert phrase in skill
        assert phrase in redo or phrase in metadata

    for phrase in [
        "single paper",
        "batch",
        "source reread",
        "MinerU Markdown",
        "TeX",
        "images",
        "PDF",
        "compare existing pages",
        "staged patch",
        "one confirmation",
        "final-source-review.json",
        "record-wiki-ingest",
        "do not write human approval",
    ]:
        assert phrase in redo


def test_skill_ui_metadata_uses_single_public_skill():
    metadata = _read(PUBLIC_SKILL / "agents" / "openai.yaml")

    assert "display_name: \"Paper Research Wiki\"" in metadata
    assert "$paper-research-wiki" in metadata
    for phrase in ["提取", "检测", "更新", "沉淀"]:
        assert phrase in metadata


def test_epi_bridge_points_to_plugin_level_experience():
    skill = _read(ROOT / "plugins" / "epi" / "skills" / "epi-paper-deposition" / "SKILL.md")
    workflow = _read(
        ROOT
        / "plugins"
        / "epi"
        / "skills"
        / "epi-paper-deposition"
        / "workflows"
        / "formal-wiki-write.md"
    )
    structure = _read(ROOT / "plugins" / "epi" / "docs" / "structure.md")
    linkage = _read(ROOT / "plugins" / "epi" / "docs" / "epi-linkage.md")

    for text in [skill, workflow, structure, linkage]:
        assert "paper-research-wiki" in text
    assert "$paper-research-wiki" in skill
    assert "提取" in skill
    assert "检测" in skill
    assert "更新" in skill
    assert "重link" in skill
