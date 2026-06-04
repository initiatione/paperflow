import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "plugins" / "epi" / "docs"
PLUGIN_ROOT = ROOT / "plugins" / "epi"


def _read(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    start = text.index(marker) + len(marker)
    next_heading = text.find("\n## ", start)
    if next_heading == -1:
        return text[start:]
    return text[start:next_heading]


def test_evaluation_doc_separates_runtime_checks_from_development_quality_loop():
    text = _read("evaluation.md")
    runtime = _section(text, "Runtime Checks")
    dev_loop = _section(text, "Development Quality Loop")

    for phrase in [
        "python scripts\\orchestrator.py dry-run",
        "python scripts\\orchestrator.py prepare-ranked",
        "python scripts\\orchestrator.py report",
        "paper-gate",
        "wiki-ingest-handoff",
        "record-human-approval",
        "wiki-ingest-trigger",
        "record-wiki-ingest",
        "zotero-sync",
        "report.md",
        "report.json",
        "run-state.json",
    ]:
        assert phrase in runtime

    for phrase in [
        "Plugin Eval",
        "epi-quality-gates",
        "benchmark",
        "before/after",
        "improvement brief",
        "evaluation-brief",
        "skill-aware-evolve proposal",
        "pytest",
        "coverage",
        "release_check_epi.ps1",
    ]:
        assert phrase not in runtime
    assert (
        "Plugin Eval -> epi-quality-gates -> benchmark -> compare before/after -> "
        "improvement brief -> skill-aware-evolve proposal"
    ) in dev_loop
    for phrase in [
        "Plugin Eval",
        "epi-quality-gates",
        "benchmark",
        "before/after",
        "improvement brief",
        "evaluation-brief",
        "skill-aware-evolve proposal",
    ]:
        assert phrase in dev_loop
    assert "separate from the runtime chain" in dev_loop


def test_linkage_doc_points_to_structure_progress_and_config_docs():
    text = _read("epi-linkage.md")

    assert "docs/structure.md" in text
    assert "docs/progress.md" in text
    assert "docs/config.md" in text
    assert "配套文档" in text


def test_structure_doc_covers_current_plugin_boundaries():
    text = _read("structure.md")

    assert "# EPI 插件结构说明" in text
    assert "<plugin-root>" in text
    assert ".codex-plugin/plugin.json" in text
    assert "scripts/build/epi/" in text
    assert "skills/" in text
    assert "config-setup" in text
    assert "paper type classification" in text
    assert "evaluation_loop.py" in text
    assert "evaluation-brief" in text
    assert "paper-gate" in text
    assert "report" in text
    assert "wiki-ingest-handoff" in text
    assert "record-human-approval" in text
    assert "wiki-ingest-trigger" in text
    assert "record-wiki-ingest" in text
    assert "git init" in text
    assert "不自动创建首个 commit" in text
    assert "`report`" in text
    assert "run report" in text
    assert "wiki_ingest_record.py" in text
    assert "wiki_ingest_approval.py" in text
    assert "wiki_ingest_trigger.py" in text
    assert "agent-mediated" in text
    assert "claim-support" in text
    assert "parse-quality-critic" in text
    assert "MinerU Markdown、TeX、images、manifest" in text
    assert "不要把安装 cache 当成开发源" in text
    assert "runtime_config.py" in text
    assert r"%USERPROFILE%\.codex\plugins\paper-search\epi\runtime.json" in text


def test_progress_doc_records_status_verification_and_next_steps():
    text = _read("progress.md")

    assert "# EPI 插件进度说明" in text
    assert "更新时间：2026-06-04" in text
    assert "高质量论文收集和整理" in text
    assert "config-setup" in text
    assert "paper-quality-critic" in text
    assert "parse-quality-critic" in text
    assert "mineru/mineru-manifest.json" in text
    assert "wiki-ingest-handoff" in text
    assert "record-human-approval" in text
    assert "record-wiki-ingest" in text
    assert "wiki_ingest_recorded" in text
    assert "287 passed in 30.16s" in text
    assert "45 passed in 10.19s" in text
    assert "pass rate `1`" in text
    assert "82/100" in text
    assert "waiting_for_human_gate" in text
    assert "ready_for_agent=false" in text
    assert "ready_after_human_approval=true" in text
    assert "当前 `plugin.json` 中的版本" in text
    assert "runtime.json" in text
    assert "venue prior" in text
    assert "query planner" in text
    assert "domain ontology" in text
    assert "two-stage retrieval" in text
    assert "citation graph" in text
    assert "evaluation set" in text
    assert "用户画像/config 驱动" in text
    assert "发布前必须重跑" in text
    assert "Plugin Eval" in text
    assert "epi-improvement-brief-v1" in text
    assert "evaluation-brief" in text
    assert "source_completeness" in text
    assert "quality_loop_sources_complete" in text
    assert "MINERU_TOKEN" in text
    assert "--skip-existing" in text
    assert "MinerU reported done but produced no Markdown output" in text


def test_linkage_doc_records_paper_discovery_bundle_and_venue_prior():
    text = _read("epi-linkage.md")

    assert "nature-academic-search" in text
    assert "scripts/query-planner.py" in text
    assert "references/mode-routing.md" in text
    assert "references/query-planner.md" in text
    assert "references/paper-type-taxonomy.md" in text
    assert "references/ranking-rubric.md" in text
    assert "references/domain-ontology.md" in text
    assert "references/source-tiers.md" in text
    assert "references/dedup-engine.md" in text
    assert "references/venue-prior.md" in text
    assert "references/two-stage-retrieval.md" in text
    assert "references/citation-graph.md" in text
    assert "references/evaluation-set.md" in text
    assert "references/workflows/multi-source-discovery.md" in text
    assert "references/anti-patterns.md" in text
    assert "query_plan" in text
    assert "research_mode" in text
    assert "paper_classification" in text
    assert "quality_gate" in text
    assert "quality_tier" in text
    assert "ranking_rubric" in text
    assert "reader/claim-support.json" in text
    assert "parse-quality-critic" in text
    assert "parse-record.json" in text
    assert "domain_focus_terms" in text
    assert "5-8 条 query variants" in text
    assert "two-stage retrieval" in text
    assert "--no-query-plan" in text
    assert "--skip-existing" in text
    assert "MinerU reported done but produced no Markdown output" in text
    assert "search-record.json.query_records" in text
    assert "venue_prior" in text
    assert "verified_metrics" in text
    assert "通用插件" in text
    assert "profile、domains、positive_keywords、negative_keywords、venue_prior" in text
    assert "verified_metrics" in text


def test_paper_discovery_chat_output_requires_priority_abstracts_and_metrics():
    skill = (PLUGIN_ROOT / "skills" / "paper-discovery" / "SKILL.md").read_text(encoding="utf-8")
    output_format = (
        PLUGIN_ROOT / "skills" / "paper-discovery" / "references" / "output-format.md"
    ).read_text(encoding="utf-8")
    linkage = _read("epi-linkage.md")

    for text in [skill, output_format, linkage]:
        assert "reading-priority" in text or "阅读优先级" in text
        assert "short Chinese abstract" in text or "中文简短摘要" in text
        assert "citation" in text or "引用数" in text
        assert "impact factor" in text or "影响因子" in text
        assert "CiteScore" in text
        assert "未核实" in text
    assert "Do not output an unsorted title-only list" in output_format
    assert "禁止返回未排序的标题清单" in linkage


def test_docs_document_easyscholar_enrichment_contract():
    attribution = _read("attribution.md")
    config = _read("config.md")
    workflow = _read("workflow.md")
    skill = (PLUGIN_ROOT / "skills" / "paper-discovery" / "SKILL.md").read_text(encoding="utf-8")
    ranking_rubric = (
        PLUGIN_ROOT / "skills" / "paper-discovery" / "references" / "ranking-rubric.md"
    ).read_text(encoding="utf-8")
    quality_gate = (
        PLUGIN_ROOT / "skills" / "paper-discovery" / "references" / "quality-gate.md"
    ).read_text(encoding="utf-8")
    output_format = (
        PLUGIN_ROOT / "skills" / "paper-discovery" / "references" / "output-format.md"
    ).read_text(encoding="utf-8")
    vendor_notice = (PLUGIN_ROOT / "vendor-notices" / "easyscholar-mcp.md").read_text(encoding="utf-8")
    combined = "\n".join([attribution, config, workflow, skill, ranking_rubric, quality_gate, output_format, vendor_notice])

    for phrase in [
        "EasyScholar",
        "chaosman42/easyscholar-mcp",
        "MIT License",
        "EASYSCHOLAR_SECRET_KEY",
        "default-on",
        "--no-easyscholar",
        "easyscholar-record.json",
        "easyscholar_score",
        "verified_metrics.easyscholar",
        "未核实",
    ]:
        assert phrase in combined
    assert "EASYSCHOLAR_SECRET_KEY=set" in config
    assert "EASYSCHOLAR_SECRET_KEY=missing" in config
    assert "secretKey" not in workflow
    assert "cannot by itself make a paper Tier A" in quality_gate


def test_human_approval_requires_single_readable_approval_report():
    paper_ingest = (PLUGIN_ROOT / "skills" / "paper-ingest" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    linkage = _read("epi-linkage.md")
    workflow = _read("workflow.md")

    for text in [paper_ingest, linkage, workflow]:
        assert "approval report" in text or "人工确认报告" in text
        assert "single" in text or "唯一" in text or "一份" in text
        assert "Chinese-English" in text or "中英对照" in text
        assert "建议沉淀" in text
        assert "谨慎沉淀" in text
        assert "暂不沉淀" in text
        assert "raw JSON" in text


def test_epi_literature_wiki_contract_documents_seven_page_families_and_research_fields():
    workflow = _read("workflow.md")
    structure = _read("structure.md")
    overview = _read("overview.zh.md")
    linkage = _read("epi-linkage.md")
    paper_ingest = (PLUGIN_ROOT / "skills" / "paper-ingest" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    wiki_provenance = (PLUGIN_ROOT / "skills" / "wiki-provenance" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    wiki_setup = (PLUGIN_ROOT / "skills" / "wiki-setup" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    epi_deposition = (
        PLUGIN_ROOT / "skills" / "epi-paper-deposition" / "SKILL.md"
    ).read_text(encoding="utf-8")
    combined = "\n".join(
        [workflow, structure, overview, linkage, paper_ingest, wiki_provenance, wiki_setup, epi_deposition]
    )

    for page_family in [
        "references/",
        "concepts/",
        "derivations/",
        "experiments/",
        "synthesis/",
        "reports/",
        "opportunities/",
    ]:
        assert page_family in workflow
        assert page_family in structure
        assert page_family in overview
        assert page_family in paper_ingest
        assert page_family in wiki_provenance
        assert page_family in wiki_setup
        assert page_family in epi_deposition

    for field in [
        "theory_reconstruction",
        "formula_derivation",
        "figure_table_evidence",
        "novelty_type",
        "implementability",
        "reproducibility_risk",
        "research_gap",
        "cost_level",
    ]:
        assert field in combined

    for skill in [
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
    ]:
        assert skill in combined

    assert "wiki_deposition_task.json" in combined
    assert "epi-wiki-deposition" in combined
    assert "compatibility" in epi_deposition or "alias" in epi_deposition

    for field in [
        "title",
        "category",
        "page_family",
        "tags",
        "aliases",
        "sources",
        "summary",
        "provenance",
        "base_confidence",
        "lifecycle",
        "lifecycle_changed",
        "tier",
        "created",
        "updated",
    ]:
        assert field in combined

    for phrase in [
        "frontmatter",
        "category",
        "page_family",
        "draft` or `review-needed`",
        "do not mark pages `source-reviewed` or `verified`",
        "forbidden formula blocks",
        "Obsidian wikilinks",
        "tag-taxonomy",
        "wiki-provenance",
        "wiki-lint",
        "wiki-stage-commit",
        "source reread",
        "formula/figure review",
        "cross-paper comparison matrix",
        "author-claimed novelty",
        "EPI-confirmed novelty",
    ]:
        assert phrase in combined


def test_plugin_project_does_not_embed_local_machine_paths():
    forbidden = [
        "C:\\Users\\liuchf",
        "D:\\paper-search",
        "D:\\paper-research-wiki",
        "D:\\codex-tmp",
    ]
    for path in PLUGIN_ROOT.rglob("*"):
        if path.is_file():
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for phrase in forbidden:
                assert phrase not in text, f"{phrase} leaked into {path}"


def test_epi_skill_architecture_alignment_documents_routing_and_closure():
    agents = (PLUGIN_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    routing = (PLUGIN_ROOT / "skills" / "routing.yaml").read_text(encoding="utf-8")
    structure = _read("structure.md")
    workflow = _read("workflow.md")
    paper_ingest = (PLUGIN_ROOT / "skills" / "paper-ingest" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    deposition = (
        PLUGIN_ROOT / "skills" / "epi-paper-deposition" / "SKILL.md"
    ).read_text(encoding="utf-8")
    run_lifecycle = (
        PLUGIN_ROOT / "skills" / "run-lifecycle" / "SKILL.md"
    ).read_text(encoding="utf-8")
    combined = "\n".join([agents, routing, structure, workflow, paper_ingest, deposition, run_lifecycle])

    assert "skills/routing.yaml" in agents
    assert "thin shell" in agents
    assert "re-match" in agents
    assert "source_bundle_audit.py" in structure
    assert "wiki_handoff_contracts.py" in structure
    assert "wiki_language.py" in structure
    assert "graph_visibility.py" in structure
    assert "cli_routes.py" in structure
    assert "wiki_record_workflows.py" in structure
    assert "write_json_atomic" in structure
    assert "task_closure" in routing
    assert "source_bundle_audit" in routing
    assert "formal_page_language_policy" in routing
    assert "codex_subagent_permission" in routing
    assert "agents/openai.yaml" in workflow
    assert "$skill-name" in workflow
    assert "workflows/*.md" in workflow
    assert "workflows` 字段" in workflow
    assert "Codex may use subagents only when the user explicitly authorizes" in combined
    assert "formal wiki page body prose defaults to Chinese" in combined
    assert "source bundle is incomplete" in combined
    assert "original constraints" in combined
    assert "30-second AAR" in combined


def test_marketplace_and_readme_describe_profile_driven_generic_epi():
    manifest = json.loads((PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    workflow = _read("workflow.md")
    overview = _read("overview.zh.md")

    manifest_text = json.dumps(manifest, ensure_ascii=False)
    assert "profile-driven academic paper discovery" in manifest_text
    assert "user's config plus the current request" in manifest_text
    assert "reader/critic review" in manifest_text
    assert "low-burden reading reports" in manifest_text
    assert "wiki handoff" in manifest_text
    assert "quality evolution" in manifest_text
    assert "Search and rank academic papers" in manifest["description"]
    assert "robotics" not in manifest["keywords"]
    assert "embodied-intelligence" not in manifest["keywords"]
    assert "control" not in manifest["keywords"]

    assert "A general academic paper intelligence workflow" in readme
    assert "searches, ranks, preserves, parses, reads, critic-checks, stages, reports" in readme
    assert "profile-driven high-quality paper collection" in readme
    assert "C:\\Users\\liuchf" not in readme
    assert "D:\\paper-research-wiki" not in readme
    assert "not a separate marketplace plugin" in readme
    assert manifest["version"] in manifest["interface"]["shortDescription"]

    assert "EPI 是通用论文插件，不默认任何学科方向" in workflow
    assert "Claude" in workflow
    assert "Codex" in workflow
    assert 'dry-run --query "<your topic>"' in workflow
    assert "prepare-ranked --run-id <run-id> --max-papers 10 --skip-existing" in workflow
    assert "prepare-ranked --run-id <run-id> --max-papers 10 --skip-existing --vault <vault> --json" in workflow
    assert "report --run-id <run-id> --vault <vault>" in workflow
    assert "report --run-id <run-id> --vault <vault> --json" in workflow
    assert "robotics embodied intelligence control" not in workflow
    assert "Claude" in overview
    assert "Codex" in overview
