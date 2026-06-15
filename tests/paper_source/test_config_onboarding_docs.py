from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG_DOC = ROOT / "plugins" / "paper-source" / "docs" / "config.md"
SKILL_DIR = ROOT / "plugins" / "paper-source" / "skills"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_config_doc_defines_plain_chinese_eight_step_onboarding_script():
    text = _read(CONFIG_DOC)

    assert "## 聊天式初始化脚本" in text
    assert "不要直接运行论文流程" in text
    assert "不懂可以直接回复：默认" in text
    assert "不要用字段名当问题标题" in text
    assert "一次只问一个问题" in text
    assert "最终确认前不得运行 `init-config`" in text

    for phrase in [
        "第一步，先定论文库放哪里",
        "第二步，我需要知道你的研究画像",
        "第三步，告诉我哪些词算有用，哪些词要避开",
        "第四步，先定搜索从哪里来",
        "第五步，定每次先看多少篇",
        "第六步，MinerU 先怎么接",
        "第七步，Zotero 要不要先连",
        "最后一步，什么时候需要你确认",
    ]:
        assert phrase in text

    assert "你刚刚选了什么" in text
    assert "技术预览" in text
    assert "YAML" in text
    assert "等用户明确确认后" in text
    assert r"%USERPROFILE%\.codex\plugins\paperflow\paper-source\runtime.json" in text
    assert "runtime.json 不保存 token 明文" in text
    assert "mineru.env" in text
    assert "Paper Source 是通用插件，不默认任何学科" in text
    assert "venue prior" in text
    assert "config-status --vault <vault> --json --include-values --include-runtime" in text


def test_config_setup_skill_owns_initialization_and_update_onboarding():
    skill_path = SKILL_DIR / "config-setup" / "SKILL.md"
    text = _read(skill_path)

    assert "name: config-setup" in text
    assert "docs\\config.md" in text
    assert "doctor" in text
    assert "config-status" in text
    assert "--include-values --include-runtime" in text
    assert "Only run `doctor`" in text
    assert "Paper Source 是通用论文插件" in text
    assert "一次只问一个问题" in text
    assert "最终确认前不得运行 `init-config`" in text
    assert "最终确认前不得运行 `apply-config-update`" in text
    assert "runtime.json" in text
    assert "不保存 token 明文" in text
    assert "YAML field names" in text
    assert "默认" in text
    assert "technical preview" in text


def test_wiki_setup_skill_owns_vault_initialization_and_reset_confirmation():
    text = _read(SKILL_DIR / "wiki-setup" / "SKILL.md")
    reset_workflow = _read(SKILL_DIR / "wiki-setup" / "workflows" / "reset-repair.md")
    recovery = _read(SKILL_DIR / "wiki-setup" / "references" / "reset-recovery.md")
    combined = "\n".join([text, reset_workflow, recovery])

    assert "name: wiki-setup" in text
    assert "scripts\\init_paper_wiki.py" in text
    assert "Initialization is idempotent" in text
    assert "git init" in text
    assert "does not create a first commit" in text
    assert "AGENTS.md" in text
    assert "_meta\\agent-operating-contract.md" in text
    assert "_meta\\directory-structure.md" in text
    assert "workflows/reset-repair.md" in text
    assert "source-first for paper research" in combined
    assert "mineru\\<slug>.md" in combined
    assert "mineru\\images\\*" in combined
    assert "Reset is destructive" in reset_workflow
    assert "wiki structure reset and Paper Source config reset are separate operations" in text
    assert "_paper_source\\meta\\paper-source-config.yaml" in text
    assert "_paper_source\\meta\\paper-source-config-state.json" in text
    assert "_paper_source\\meta\\config-history\\" in text
    assert "_paper_source\\README.md" in combined
    assert "_paper_source\\manifest.json" in combined
    assert "_paper_source\\policies\\retention.json" in combined
    assert "retention policy must cap lifecycle artifacts" in combined
    assert "formal-page-snapshots" in combined
    assert "tmp-manual-pdfs" in combined
    assert "no-write inspection" in combined
    assert "paper-source-repository-migrate --vault <vault> --preview --json" in text
    assert "paper-source-repository-cleanup --vault <vault> --preview --json" in text
    assert r"%USERPROFILE%\.codex\plugins\paperflow\paper-source\runtime.json" in text
    assert "config-status --vault <vault> --json --include-values --include-runtime" in reset_workflow
    assert "确认重置 Paper Source wiki" in reset_workflow
    assert "确认同时重置 Paper Source config" in reset_workflow
    assert "wiki-reset --vault <vault> --preview --json" in reset_workflow
    assert "wiki-reset --vault <vault>" in reset_workflow
    assert "--reset-config-confirmed-by" in reset_workflow
    assert "不需要备份" in reset_workflow
    assert "do not back up wiki content" in reset_workflow
    assert "Repair And Recovery" in reset_workflow
    assert "误删" in reset_workflow
    assert "without the exact second confirmation" in reset_workflow
    assert "wiki-repair --vault <vault> --json" in recovery
    assert "config-recover --vault <vault> --json" in recovery
    assert "config-restore --vault <vault>" in recovery
    assert "确认恢复 Paper Source config" in recovery
    assert "Actively ask whether the user wants help restoring important settings" in recovery
    assert "<vault-parent>\\paper-research-wiki-reset-backups\\" in recovery
    assert "backup outside the active vault" in recovery


def test_paper_source_skills_delegate_onboarding_wording_to_config_doc():
    for skill_name in [
        "paper-discovery",
        "paper-ingest",
        "zotero-sync",
        "skill-aware-evolve",
    ]:
        text = _read(SKILL_DIR / skill_name / "SKILL.md")

        assert "docs\\config.md" in text
        assert "config-setup" in text


def test_paper_source_skills_document_precise_one_to_three_prepare_ranked_path():
    discovery = _read(SKILL_DIR / "paper-discovery" / "SKILL.md")
    ingest = _read(SKILL_DIR / "paper-ingest" / "SKILL.md")
    discovery_workflow = _read(SKILL_DIR / "paper-discovery" / "workflows" / "run-discovery.md")
    ingest_prepare = _read(SKILL_DIR / "paper-ingest" / "workflows" / "prepare-ranked.md")
    ingest_approval = _read(SKILL_DIR / "paper-ingest" / "workflows" / "approval-and-trigger.md")
    mineru = _read(SKILL_DIR / "mineru-paper-parser" / "SKILL.md")
    combined = "\n".join([discovery, ingest, discovery_workflow, ingest_prepare, ingest_approval])

    assert "prepare-ranked" in discovery
    assert "workflows/run-discovery.md" in discovery
    assert "workflows/prepare-ranked.md" in ingest
    assert "workflows/approval-and-trigger.md" in ingest
    assert "--max-papers 10" in ingest_prepare
    assert "--skip-existing" in ingest_prepare
    assert "smoke test" in ingest_prepare
    assert "profile-derived" in discovery_workflow
    assert "source-staging" in combined
    assert "acquire-record.json" in ingest_prepare
    assert "parse-record.json" in ingest_prepare
    assert "fast-ingest" in ingest
    assert "reviewed-ingest" in ingest
    assert "audited-ingest" in ingest
    assert "Source-First Handoff Check" in ingest_prepare
    assert "report --run-id <run-id>" in discovery_workflow
    assert "mineru/<slug>.md" in ingest_prepare
    assert "mineru/images/*" in ingest_prepare
    assert "formula/figure review cues" in ingest_prepare
    assert "not source authority" in ingest
    assert "tex_source=paused-no-native-tex" in mineru
    assert "mineru-command\\paper" in mineru
    assert "mineru-command\\parsed" in mineru
    assert "MinerU reported done but produced no Markdown output" in mineru


def test_paper_discovery_skill_documents_quality_first_chat_recommendations():
    discovery = _read(SKILL_DIR / "paper-discovery" / "SKILL.md")
    discovery_workflow = _read(SKILL_DIR / "paper-discovery" / "workflows" / "run-discovery.md")

    assert "references/query-planner.md" in discovery
    assert "references/mode-routing.md" in discovery
    assert "references/paper-type-taxonomy.md" in discovery
    assert "references/ranking-rubric.md" in discovery
    assert "references/domain-ontology.md" in discovery
    assert "references/output-format.md" in discovery
    assert "references/anti-patterns.md" in discovery
    assert "references/search-protocol.md" in discovery
    assert "references/source-tiers.md" in discovery
    assert "references/dedup-engine.md" in discovery
    assert "references/venue-prior.md" in discovery
    assert "references/two-stage-retrieval.md" in discovery
    assert "references/citation-graph.md" in discovery
    assert "references/evaluation-set.md" in discovery
    assert "workflows/multi-source-discovery.md" in discovery
    assert "references/quality-gate.md" in discovery
    assert "The full Paper Source chain stays documented" in discovery or "docs\\paper-source-linkage.md" in discovery
    assert "read-priority reporting" in discovery_workflow


def test_paper_discovery_skill_defines_stronger_high_quality_search_protocol():
    discovery = _read(SKILL_DIR / "paper-discovery" / "SKILL.md")
    discovery_workflow = _read(SKILL_DIR / "paper-discovery" / "workflows" / "run-discovery.md")

    assert "query-planner.py" in discovery_workflow
    assert "--no-query-plan" in discovery_workflow
    assert "references/query-planner.md" in discovery
    assert "references/mode-routing.md" in discovery
    assert "references/paper-type-taxonomy.md" in discovery
    assert "references/ranking-rubric.md" in discovery
    assert "references/domain-ontology.md" in discovery
    assert "references/search-protocol.md" in discovery
    assert "references/source-tiers.md" in discovery
    assert "references/dedup-engine.md" in discovery
    assert "references/venue-prior.md" in discovery
    assert "references/two-stage-retrieval.md" in discovery
    assert "references/citation-graph.md" in discovery
    assert "references/evaluation-set.md" in discovery
    assert "workflows/multi-source-discovery.md" in discovery
    assert "references/quality-gate.md" in discovery
    assert "references/output-format.md" in discovery
    assert "references/anti-patterns.md" in discovery
    assert "The full Paper Source chain stays documented" in discovery or "docs\\paper-source-linkage.md" in discovery


def test_paper_discovery_reference_files_exist_and_hold_split_protocol():
    query_planner = _read(SKILL_DIR / "paper-discovery" / "references" / "query-planner.md")
    mode_routing = _read(SKILL_DIR / "paper-discovery" / "references" / "mode-routing.md")
    paper_type_taxonomy = _read(SKILL_DIR / "paper-discovery" / "references" / "paper-type-taxonomy.md")
    ranking_rubric = _read(SKILL_DIR / "paper-discovery" / "references" / "ranking-rubric.md")
    domain_ontology = _read(SKILL_DIR / "paper-discovery" / "references" / "domain-ontology.md")
    search_protocol = _read(SKILL_DIR / "paper-discovery" / "references" / "search-protocol.md")
    source_tiers = _read(SKILL_DIR / "paper-discovery" / "references" / "source-tiers.md")
    dedup_engine = _read(SKILL_DIR / "paper-discovery" / "references" / "dedup-engine.md")
    venue_prior = _read(SKILL_DIR / "paper-discovery" / "references" / "venue-prior.md")
    two_stage = _read(SKILL_DIR / "paper-discovery" / "references" / "two-stage-retrieval.md")
    citation_graph = _read(SKILL_DIR / "paper-discovery" / "references" / "citation-graph.md")
    evaluation_set = _read(SKILL_DIR / "paper-discovery" / "references" / "evaluation-set.md")
    workflow = _read(
        SKILL_DIR
        / "paper-discovery"
        / "workflows"
        / "multi-source-discovery.md"
    )
    quality_gate = _read(SKILL_DIR / "paper-discovery" / "references" / "quality-gate.md")
    output_format = _read(SKILL_DIR / "paper-discovery" / "references" / "output-format.md")
    anti_patterns = _read(SKILL_DIR / "paper-discovery" / "references" / "anti-patterns.md")

    assert "5-8 query variants" in query_planner
    assert "`research_mode`" in query_planner
    assert "targeted-discovery" in mode_routing
    assert "systematic-review" in mode_routing
    assert "paper_type" in paper_type_taxonomy
    assert "classification_confidence" in paper_type_taxonomy
    assert "ranking_confidence" in ranking_rubric
    assert "source_confidence" in ranking_rubric
    assert "AUV / Marine Control" in domain_ontology
    assert "autonomous underwater vehicle" in domain_ontology
    assert "5-8 query variants" in search_protocol
    assert "--no-query-plan" in search_protocol
    assert "profile or current request" in search_protocol
    assert "hard_domain_anchors" in search_protocol
    assert "soft_recall_terms" in search_protocol
    assert "targeted verification fallback only after a Paper Source candidate or run artifact exists" in search_protocol
    assert "Do not use Firecrawl, generic web search, publisher search, or GitHub search as the primary discovery provider" in search_protocol
    assert "Default to `dry-run` resume" in search_protocol
    assert "Treat repository checks as code evidence verification, not as paper discovery" in search_protocol
    assert "publisher PDF blocks" in search_protocol
    assert "two-stage-retrieval.md" in search_protocol
    assert "citation-graph.md" in search_protocol
    assert "paper_search_mcp" in search_protocol
    assert "source tier" in source_tiers.lower()
    assert "field community lists" in source_tiers
    assert "DOI" in dedup_engine
    assert "_meta\\reference-index.json" in dedup_engine
    assert "already_in_wiki:<page>" in dedup_engine
    assert "already_in_library:<slug>" in dedup_engine
    assert "venue_prior" in venue_prior
    assert "configured or curated prior" in venue_prior
    assert "Domain examples, not defaults" in venue_prior
    assert "Robotics/control profiles may list" in venue_prior
    assert "High Recall Candidate Pool" in two_stage
    assert "query-plan.json" in two_stage
    assert "hard_domain_anchors" in two_stage
    assert "precision_at_10" in evaluation_set
    assert "recent cited-by" in citation_graph
    assert "query_plan" in workflow
    assert "verified_metrics" in workflow
    assert "Tier A" in quality_gate
    assert "paper-type-taxonomy.md" in quality_gate
    assert "Two-stage retrieval" in quality_gate
    assert "venue-prior.md" in quality_gate
    assert "recall gap" in quality_gate
    assert "method family" in quality_gate
    assert "推荐优先看" in output_format
    assert "query_plan_multi_query" in output_format
    assert "venue prior" in output_format
    assert "quality_tier" in output_format
    assert "quality_gate" in output_format
    assert "ranking_confidence" in output_format
    assert "citation graph expansion" in output_format
    assert "Paper Source 实测证据" in output_format
    assert "Method-only leakage" in anti_patterns
    assert "Do not present a Firecrawl/web-only result set as a Paper Source recommendation" in output_format
    assert "Web-first discovery" in anti_patterns
    assert "Repeat provider loop" in anti_patterns
    assert "Repository as paper identity" in anti_patterns


def test_paper_ingest_source_first_reading_reference_exists():
    ingest = _read(SKILL_DIR / "paper-ingest" / "SKILL.md")
    source_first = _read(SKILL_DIR / "paper-ingest" / "references" / "source-first-reading.md")

    assert "references/source-first-reading.md" in ingest
    assert "Claim Cards" in source_first
    assert "Formula And Figure Rules" in source_first
    assert "`mineru/paper.tex` only when non-empty native TeX exists" in source_first
    assert "mineru/images/*" in source_first
    assert "reader/claim-support.json" in source_first
