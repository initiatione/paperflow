import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "plugins" / "paper-source" / "docs"
PLUGIN_ROOT = ROOT / "plugins" / "paper-source"


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
        "paper-source-quality-gates",
        "benchmark",
        "before/after",
        "improvement brief",
        "evaluation-brief",
        "skill-aware-evolve proposal",
        "pytest",
        "coverage",
        "release_check_paper_source.ps1",
    ]:
        assert phrase not in runtime
    assert (
        "Plugin Eval -> paper-source-quality-gates -> benchmark -> compare before/after -> "
        "improvement brief -> skill-aware-evolve proposal"
    ) in dev_loop
    for phrase in [
        "Plugin Eval",
        "paper-source-quality-gates",
        "benchmark",
        "before/after",
        "improvement brief",
        "evaluation-brief",
        "skill-aware-evolve proposal",
    ]:
        assert phrase in dev_loop
    assert "separate from the runtime chain" in dev_loop


def test_linkage_doc_points_to_structure_progress_and_config_docs():
    text = _read("paper-source-linkage.md")

    assert "docs/structure.md" in text
    assert "docs/progress.md" in text
    assert "docs/config.md" in text
    assert "配套文档" in text


def test_root_plugin_development_rules_require_version_and_doc_sync():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    rules_path = ROOT / "docs" / "plugin-development.md"
    rules = rules_path.read_text(encoding="utf-8")

    assert "docs/plugin-development.md" in readme
    assert "每次改动插件源码" in readme
    assert "同步插件版本信息" in readme
    assert "源码验证通过不等于安装缓存已经更新" in readme

    for phrase in [
        "任何插件改动都必须同步版本信息",
        "plugins/<plugin>/.codex-plugin/plugin.json",
        "interface.shortDescription",
        "PaperFlow",
        "Paper Source",
        "Paper Wiki",
        "display name",
        "machine names",
        "`paper-source`",
        "`paper-wiki`",
        "pre-Stage-2",
        "PS/PW",
        "开发完成后必须同步文档信息",
        "$skill-creator",
        "D:\\paper-search\\.codex_tmp_refs\\skill-based-architecture",
        "rules/workflows/references 分层",
        "禁止把安装 cache 当作开发源",
        "源码验证通过不等于用户运行态已更新",
        "Paper Wiki 不初始化、修复、reset 或静默创建 vault 结构",
        "每次插件开发收尾必须报告",
    ]:
        assert phrase in rules

    for command in [
        "python -m pytest tests\\paper_research_wiki\\test_plugin_contract.py plugins\\paper-source\\tests\\test_skill_bundle_contract.py tests\\test_marketplace_manifest.py -q",
        "python -m json.tool plugins\\paper-source\\.codex-plugin\\plugin.json",
        "python -m json.tool plugins\\paper-wiki\\.codex-plugin\\plugin.json",
        "PLUGIN_VALIDATE_SCRIPT",
        "git diff --check",
    ]:
        assert command in rules


def test_root_readme_documents_paperflow_stage2_names_and_legacy_aliases():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for phrase in [
        "PaperFlow",
        "Paper Source",
        "Paper Wiki",
        "PS",
        "PW",
        "`paperflow`",
        "`paper-source`",
        "`paper-wiki`",
        "`epi`",
        "`prw`",
        "machine-facing",
        "legacy alias",
        "pre-Stage-2",
    ]:
        assert phrase in readme

    assert "Paper Source 机器名" in readme
    assert "Paper Wiki 机器名" in readme


def test_structure_doc_covers_current_plugin_boundaries():
    text = _read("structure.md")

    assert "# Paper Source 插件结构说明" in text
    assert "<plugin-root>" in text
    assert ".codex-plugin/plugin.json" in text
    assert "scripts/build/paper_source/" in text
    assert "legacy import shim" in text
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
    assert "raw_cleanup.py" in text
    assert "candidate_pdf_urls" in text
    assert "paper_search_mcp.env_file" in text
    assert r"%USERPROFILE%\.codex\plugins\paperflow\paper-source\runtime.json" in text


def test_progress_doc_records_status_verification_and_next_steps():
    text = _read("progress.md")

    assert "# Paper Source 插件进度说明" in text
    assert "更新时间：2026-06-08" in text
    assert "高质量论文收集和整理" in text
    assert "config-setup" in text
    assert "paper-quality-critic" in text
    assert "parse-quality-critic" in text
    assert "mineru/mineru-manifest.json" in text
    assert "wiki-ingest-handoff" in text
    assert "record-human-approval" in text
    assert "record-wiki-ingest" in text
    assert "wiki_ingest_recorded" in text
    assert "107 passed in 1.35s" in text
    assert "55 passed in 0.42s" in text
    assert "70 passed in 1.16s" in text
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
    assert "paper-source-improvement-brief-v1" in text
    assert "evaluation-brief" in text
    assert "source_completeness" in text
    assert "quality_loop_sources_complete" in text
    assert "MINERU_TOKEN" in text
    assert "--skip-existing" in text
    assert "MinerU reported done but produced no Markdown output" in text


def test_linkage_doc_records_paper_discovery_bundle_and_venue_prior():
    text = _read("paper-source-linkage.md")

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
    assert "workflows/multi-source-discovery.md" in text
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
    linkage = _read("paper-source-linkage.md")

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
    assert "easyscholar.env_file" in config
    assert "secretKey" not in workflow
    assert "cannot by itself make a paper Tier A" in quality_gate


def test_docs_document_landing_page_acquisition_recovery():
    prepare_ranked = (
        PLUGIN_ROOT / "skills" / "paper-ingest" / "workflows" / "prepare-ranked.md"
    ).read_text(encoding="utf-8")
    search_protocol = (
        PLUGIN_ROOT / "skills" / "paper-discovery" / "references" / "search-protocol.md"
    ).read_text(encoding="utf-8")
    combined = "\n".join([prepare_ranked, search_protocol])

    for phrase in [
        "not-pdf",
        "citation_pdf_url",
        "landing page",
        "publisher PDF link",
        "candidate_pdf_urls",
        "acquire_attempts",
        "Unpaywall",
    ]:
        assert phrase in combined


def test_docs_document_paper_search_mcp_fallback_and_source_coverage():
    manifest = json.loads((PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    mcp_config = (PLUGIN_ROOT / ".mcp.json").read_text(encoding="utf-8")
    attribution = _read("attribution.md")
    config = _read("config.md")
    linkage = _read("paper-source-linkage.md")
    privacy = _read("privacy.md")
    progress = _read("progress.md")
    structure = _read("structure.md")
    terms = _read("terms.md")
    workflow = _read("workflow.md")
    vendor_notice = (PLUGIN_ROOT / "vendor-notices" / "paper-search-mcp.md").read_text(encoding="utf-8")
    search_protocol = (
        PLUGIN_ROOT / "skills" / "paper-discovery" / "references" / "search-protocol.md"
    ).read_text(encoding="utf-8")
    prepare_ranked = (
        PLUGIN_ROOT / "skills" / "paper-ingest" / "workflows" / "prepare-ranked.md"
    ).read_text(encoding="utf-8")
    combined = "\n".join(
        [
            json.dumps(manifest, ensure_ascii=False),
            mcp_config,
            attribution,
            config,
            linkage,
            privacy,
            progress,
            structure,
            terms,
            workflow,
            vendor_notice,
            search_protocol,
            prepare_ranked,
        ]
    )

    assert manifest["version"] == "0.2.1"
    assert "v0.2.1" in manifest["interface"]["shortDescription"]
    for phrase in [
        "search_papers",
        "source_coverage",
        "Source Coverage",
        "sources_used",
        "source_results",
        "raw_total",
        "deduped_total",
        "query_count",
        "download_with_fallback",
        "fallback_chain",
        "use_scihub",
        "PAPER_SOURCE_PAPER_SEARCH_MCP_USE_SCIHUB=1",
        "Sci-Hub 默认关闭",
        "Sci-Hub is disabled",
        "OpenAIRE",
        "Europe PMC",
        "mcp_server_probe",
        "upstream.tool",
        "retrieval_preview",
        "paper-search-read-preview.txt",
        "read_<source>_paper",
        "CLI read",
        "non-authoritative",
        "not replacing MinerU",
        "sidecar",
        "manual_download",
        "manual-download-required",
        "candidate_manual_urls",
        "organization/institution",
        "paper_search_provider_readiness",
        "provider_readiness",
        "source_routing",
        "provider_gaps",
        "unpaywall_email_missing",
        "mcp_outer_launcher",
        "codex_mcp_registration",
        "adaptive Python detection",
        "import paper_search_mcp",
        "capabilities",
        "PAPER_SEARCH_MCP_CORE_API_KEY",
        "PAPER_SEARCH_MCP_GOOGLE_SCHOLAR_PROXY_URL",
        "Google Scholar",
        "unstable",
        "identity-check.json",
        "identity-mismatch",
        "_paper_source/quarantine/papers",
        "quarantine",
        "source capability matrix",
        "wiki-ask",
        "read-only formal graph",
        "0.2.1",
        "0.1.14",
        "0.1.11",
        "0.1.13",
        "0.1.12",
        "0.1.10",
        "0.1.8",
        "installed cache",
    ]:
        assert phrase in combined


def test_docs_document_bounded_paper_source_lifecycle_cleanup_contract():
    manifest = json.loads((PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    linkage = _read("paper-source-linkage.md")
    progress = _read("progress.md")
    structure = _read("structure.md")
    wiki_setup = (PLUGIN_ROOT / "skills" / "wiki-setup" / "SKILL.md").read_text(encoding="utf-8")
    combined = "\n".join([json.dumps(manifest, ensure_ascii=False), linkage, progress, structure, wiki_setup])

    for phrase in [
        "bounded lifecycle cleanup",
        "retention.json",
        "3000 files",
        "1 GiB",
        "lifecycle 上限",
        "no-write inspection",
        "over_budget=false",
        "run-lifecycle",
        "raw-cleanup",
        "repository-maintenance",
        "migrations",
        "wiki-reset",
        "formal-page-snapshots",
        "tmp-manual-pdfs",
        "不刷新 `_paper_source/manifest.json`",
        "不得删除 `_paper_source/raw`",
    ]:
        assert phrase in combined


def test_docs_document_failed_raw_cleanup_and_provider_env_file():
    config = _read("config.md")
    workflow = _read("workflow.md")
    structure = _read("structure.md")
    combined = "\n".join([config, workflow, structure])

    for phrase in [
        "paper_search_mcp.env_file",
        "PAPER_SEARCH_MCP_UNPAYWALL_EMAIL",
        "raw_cleanup.py",
        "_paper_source/meta/raw-cleanup/",
        "failed attempts do not accumulate as library entries",
    ]:
        assert phrase in combined


def test_human_approval_requires_single_readable_approval_report():
    paper_ingest = (PLUGIN_ROOT / "skills" / "paper-ingest" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    linkage = _read("paper-source-linkage.md")
    workflow = _read("workflow.md")

    for text in [paper_ingest, linkage, workflow]:
        assert "approval report" in text or "人工确认报告" in text
        assert "single" in text or "唯一" in text or "一份" in text
        assert "Chinese-English" in text or "中英对照" in text
        assert "建议沉淀" in text
        assert "谨慎沉淀" in text
        assert "暂不沉淀" in text
        assert "raw JSON" in text


def test_docs_document_prw_reviewed_record_correction_return_path():
    workflow = _read("workflow.md")
    linkage = _read("paper-source-linkage.md")
    approval = (
        PLUGIN_ROOT
        / "skills"
        / "paper-ingest"
        / "workflows"
        / "approval-and-trigger.md"
    ).read_text(encoding="utf-8")
    paper_ingest = (PLUGIN_ROOT / "skills" / "paper-ingest" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    combined = "\n".join([workflow, linkage, approval, paper_ingest])

    for phrase in [
        "premature-wiki-ingest-record",
        "record-corrections",
        "pending-paper-wiki-review",
        "paper-wiki-reviewed-ready-for-paper-source-record",
        "ready_for_wiki_ingest_agent",
        "rerun `record-wiki-ingest`",
        "replace the premature record",
        "Paper Wiki repairs pages and `final-source-review.json`; Paper Source writes or replaces `wiki-ingest-record.json`",
    ]:
        assert phrase in combined


def test_docs_document_prw_record_request_ask_mode_automation():
    workflow = _read("workflow.md")
    linkage = _read("paper-source-linkage.md")
    approval = (
        PLUGIN_ROOT
        / "skills"
        / "paper-ingest"
        / "workflows"
        / "approval-and-trigger.md"
    ).read_text(encoding="utf-8")
    paper_ingest = (PLUGIN_ROOT / "skills" / "paper-ingest" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    combined = "\n".join([workflow, linkage, approval, paper_ingest])

    for phrase in [
        "paper-wiki-record-request.json",
        "paper-wiki-record-request-v1",
        "automation_mode=ask",
        "record-wiki-ingest --from-paper-wiki-request",
        "Paper Source validates live page hashes",
        "Paper Wiki writes the request artifact; Paper Source consumes it",
    ]:
        assert phrase in combined


def test_paper_source_literature_wiki_contract_documents_seven_page_families_and_research_fields():
    workflow = _read("workflow.md")
    structure = _read("structure.md")
    overview = _read("overview.zh.md")
    linkage = _read("paper-source-linkage.md")
    paper_ingest = (PLUGIN_ROOT / "skills" / "paper-ingest" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    wiki_provenance = (PLUGIN_ROOT / "skills" / "wiki-provenance" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    wiki_setup = (PLUGIN_ROOT / "skills" / "wiki-setup" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    progress = _read("progress.md")
    epi_deposition = (
        PLUGIN_ROOT / "skills" / "paper-source-paper-deposition" / "SKILL.md"
    ).read_text(encoding="utf-8")
    combined = "\n".join(
        [
            workflow,
            structure,
            overview,
            linkage,
            paper_ingest,
            wiki_provenance,
            wiki_setup,
            progress,
            epi_deposition,
        ]
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

    for phrase in [
        "wiki-ingest-brief.json",
        "canonical Paper Source-to-Paper Wiki handoff",
        "wiki_deposition_task.json is legacy",
        "paper-research-wiki",
        "paper-source-paper-deposition",
        "external wiki skills are optional helpers",
    ]:
        assert phrase in combined

    for helper in [
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
        assert helper in combined

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
        "Paper Source-confirmed novelty",
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


def test_paper_source_skill_architecture_alignment_documents_routing_and_closure():
    agents = (PLUGIN_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    routing = (PLUGIN_ROOT / "skills" / "routing.yaml").read_text(encoding="utf-8")
    structure = _read("structure.md")
    workflow = _read("workflow.md")
    paper_ingest = (PLUGIN_ROOT / "skills" / "paper-ingest" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    deposition = (
        PLUGIN_ROOT / "skills" / "paper-source-paper-deposition" / "SKILL.md"
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
    assert "skill_bundle_contract" in workflow
    assert "agent_metadata_count" in workflow
    assert "workflow_count" in workflow
    assert "Codex may use subagents only when the user explicitly authorizes" in combined
    assert "formal wiki page body prose defaults to Chinese" in combined
    assert "source bundle is incomplete" in combined
    assert "original constraints" in combined
    assert "30-second AAR" in combined


def test_marketplace_and_readme_describe_profile_driven_generic_paper_source():
    manifest = json.loads((PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    workflow = _read("workflow.md")
    overview = _read("overview.zh.md")

    manifest_text = json.dumps(manifest, ensure_ascii=False)
    assert manifest["interface"]["displayName"] == "Paper Source"
    assert "Paper Source" in manifest_text
    assert "Paper Wiki" in manifest_text
    assert manifest["description"].startswith("Paper Source discovers")
    assert manifest["interface"]["shortDescription"].startswith("v0.2.1 | Paper Source:")
    assert "profile-driven academic paper discovery" in manifest_text
    assert "user's config plus the current request" in manifest_text
    assert "reader/critic review" in manifest_text
    assert "low-burden reading reports" in manifest_text
    assert "Paper Wiki handoff" in manifest_text
    assert "quality evolution" in manifest_text
    assert "MinerU parsing" in manifest_text
    assert "Paper Wiki handoff" in manifest_text
    assert "Paper Wiki-compatible vault" in manifest["description"]
    assert "hand off to Paper Wiki" in manifest["interface"]["shortDescription"]
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

    assert "Paper Source 是通用论文插件，不默认任何学科方向" in workflow
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


def test_docs_document_resumable_reviews_and_evidence_index():
    workflow = (ROOT / "plugins" / "paper-source" / "docs" / "workflow.md").read_text(encoding="utf-8")
    structure = (ROOT / "plugins" / "paper-source" / "docs" / "structure.md").read_text(encoding="utf-8")
    discovery = (
        ROOT / "plugins" / "paper-source" / "skills" / "paper-discovery" / "workflows" / "run-discovery.md"
    ).read_text(encoding="utf-8")
    ingest = (
        ROOT / "plugins" / "paper-source" / "skills" / "paper-ingest" / "workflows" / "prepare-ranked.md"
    ).read_text(encoding="utf-8")
    provenance = (
        ROOT / "plugins" / "paper-source" / "skills" / "wiki-provenance" / "SKILL.md"
    ).read_text(encoding="utf-8")
    combined = "\n".join([workflow, structure, discovery, ingest, provenance])
    assert "_paper_source/reviews" in combined
    assert "default resume" in combined or "默认自动 resume" in combined
    assert "--refresh" in combined
    assert "evidence-index.json" in combined
    assert "_paper_source/meta/evidence-index.json" in combined


def test_linkage_doc_enforces_paper_source_first_discovery_boundary():
    linkage = _read("paper-source-linkage.md")

    for phrase in [
        "Paper Source run/candidate artifact",
        "paper_search_mcp.search_papers",
        "Firecrawl",
        "generic web search",
        "GitHub search",
        "targeted verification",
        "primary discovery provider",
        "Firecrawl/web-only result set",
        "_paper_source/reviews/<review-id>/",
        "report --run-id",
        "--refresh",
        "reproducibility/code evidence verification",
        "paper identity discovery",
    ]:
        assert phrase in linkage


def test_paper_source_plugin_description_reflects_full_pipeline():
    manifest = json.loads((PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    desc = manifest["description"]

    assert desc != "Search and rank academic papers for an Paper Source wiki."
    assert any(k in desc for k in ["parse", "MinerU", "critic", "handoff", "wiki ingest"])


def test_paper_source_user_docs_use_paper_source_and_paper_wiki_stage2_names():
    combined = "\n".join([
        _read("workflow.md"),
        _read("structure.md"),
        _read("paper-source-linkage.md"),
    ])

    for phrase in [
        "Paper Source",
        "Paper Wiki",
        "PS/PW",
        "machine-facing name",
        "`paper-source`",
        "`paper-wiki`",
        "pre-Stage-2",
    ]:
        assert phrase in combined

    for phrase in [
        "wiki-ingest-brief.json",
        "wiki_deposition_task.json is legacy",
        "canonical Paper Source-to-Paper Wiki handoff",
    ]:
        assert phrase in combined


def test_short_aliases_do_not_create_ps_pw_machine_entrypoints():
    checked_files = [
        ROOT / "marketplace.json",
        ROOT / ".agents" / "plugins" / "marketplace.json",
        ROOT / "plugins" / "paper-source" / ".codex-plugin" / "plugin.json",
        ROOT / "plugins" / "paper-wiki" / ".codex-plugin" / "plugin.json",
        ROOT / "plugins" / "paper-source" / "skills" / "routing.yaml",
        ROOT / "plugins" / "paper-wiki" / "skills" / "routing.yaml",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in checked_files)

    assert ("$" + "PS") not in combined
    assert ("$" + "PW") not in combined
    assert ('"name": "' + "ps" + '"') not in combined.lower()
    assert ('"name": "' + "pw" + '"') not in combined.lower()
    assert ("name: " + "ps") not in combined.lower()
    assert ("name: " + "pw") not in combined.lower()


def test_orchestrator_uses_write_json_atomic_without_private_alias():
    text = (PLUGIN_ROOT / "scripts" / "build" / "paper_source" / "orchestrator.py").read_text(encoding="utf-8")

    assert "def _write_json" not in text
    assert "_write_json(" not in text
    assert "write_json_atomic(" in text


def test_handoff_artifact_contract_marks_brief_canonical_and_task_deprecated():
    linkage = _read("paper-source-linkage.md")

    assert "wiki-ingest-brief.json" in linkage
    assert "wiki_deposition_task.json" in linkage
    assert "canonical Paper Source-to-Paper Wiki handoff" in linkage
    assert "wiki_deposition_task.json is legacy" in linkage
    assert "deprecated" in linkage.lower() or "已废弃" in linkage


def test_single_doc_map_in_linkage_others_point_to_it():
    linkage = _read("paper-source-linkage.md")

    for ref in [
        "docs/structure.md",
        "docs/progress.md",
        "docs/config.md",
        "docs/overview.zh.md",
        "docs/workflow.md",
    ]:
        assert ref in linkage
    for name in ["overview.zh.md", "structure.md", "progress.md"]:
        assert "docs/paper-source-linkage.md" in _read(name)


def test_overview_zh_is_navigation_not_second_pipeline():
    text = _read("overview.zh.md")

    assert text.count("\n") < 200
    assert "docs/paper-source-linkage.md" in text
    assert ("三层" in text) or ("心智模型" in text)
    assert ("推荐阅读顺序" in text) or ("阅读顺序" in text)


def test_workflow_md_is_short_entry_without_runbook_paragraphs():
    text = _read("workflow.md")
    longest_line = max((len(line) for line in text.splitlines()), default=0)

    assert longest_line < 1200
    assert "paper-source-linkage" in text
    assert "EasyScholar" in text or "easyscholar" in text


def test_progress_md_snapshot_history_in_changelog():
    progress = _read("progress.md")
    changelog_path = DOCS / "CHANGELOG.md"

    assert changelog_path.exists()
    changelog = changelog_path.read_text(encoding="utf-8")
    assert "本轮相关变更范围" not in progress
    assert "下一步" in progress and "已知风险" in progress
    assert "CHANGELOG.md" in progress
    assert len(changelog.splitlines()) > 20


def test_progress_doc_names_s3b_as_current_boundary_work():
    progress = _read("progress.md")
    changelog = (DOCS / "CHANGELOG.md").read_text(encoding="utf-8")

    assert "S3a 文档/契约 canonical 化已完成" in progress
    assert "S3b brief-first machine-contract" in progress
    assert "wiki-ingest-brief.json" in progress
    assert "canonical Paper Source-to-Paper Wiki handoff" in progress
    assert "wiki_deposition_task.json is legacy" in progress
    assert "external wiki skills are optional helpers" in progress
    assert "REQUIRED_WIKI_SKILLS" in progress
    assert "S3a 文档/契约 canonical 化" in changelog
    assert "完成 S3a 文档/契约 canonical 化并验证" not in progress


def test_paper_source_docs_point_to_prw_canonical_for_page_family_frontmatter():
    assert "rules/wiki-writing-standard.md" in _read("paper-source-linkage.md")


def test_read_only_ask_ownership_documented_paper_source_side():
    linkage = _read("paper-source-linkage.md")

    assert "wiki-ask" in linkage
    assert ("fallback" in linkage.lower()) or ("程序化" in linkage) or ("对话优先 Paper Wiki" in linkage)


def test_plugin_versions_bumped_to_0_2_1():
    for rel in ["plugins/paper-source/.codex-plugin/plugin.json", "plugins/paper-wiki/.codex-plugin/plugin.json"]:
        manifest = json.loads((ROOT / rel).read_text(encoding="utf-8"))

        assert manifest["version"] == "0.2.1"
        assert "v0.2.1" in manifest["interface"]["shortDescription"]
