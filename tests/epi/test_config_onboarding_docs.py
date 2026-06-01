from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG_DOC = ROOT / "plugins" / "epi" / "docs" / "config.md"
SKILL_DIR = ROOT / "plugins" / "epi" / "skills"


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
    assert r"%USERPROFILE%\.codex\plugins\paper-search\epi\runtime.json" in text
    assert "runtime.json 不保存 token 明文" in text
    assert "mineru.env" in text
    assert "EPI 是通用插件，不默认任何学科" in text
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
    assert "EPI 是通用论文插件" in text
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
    recovery = _read(SKILL_DIR / "wiki-setup" / "references" / "reset-recovery.md")

    assert "name: wiki-setup" in text
    assert "scripts\\init_paper_wiki.py" in text
    assert "Initialization is idempotent" in text
    assert "git init" in text
    assert "does not create a first commit" in text
    assert "AGENTS.md" in text
    assert "_meta\\agent-operating-contract.md" in text
    assert "_meta\\directory-structure.md" in text
    assert "source-first for paper research" in text
    assert "mineru\\paper.md" in text
    assert "mineru\\images\\*" in text
    assert "Reset is destructive" in text
    assert "wiki structure reset and EPI config reset are separate operations" in text
    assert "_epi\\meta\\epi-config.yaml" in text
    assert "_epi\\meta\\epi-config-state.json" in text
    assert "_epi\\meta\\config-history\\" in text
    assert "_epi\\README.md" in text
    assert "_epi\\manifest.json" in text
    assert "_epi\\policies\\retention.json" in text
    assert "epi-repository-migrate --vault <vault> --preview --json" in text
    assert "epi-repository-cleanup --vault <vault> --preview --json" in text
    assert r"%USERPROFILE%\.codex\plugins\paper-search\epi\runtime.json" in text
    assert "config-status --vault <vault> --json --include-values --include-runtime" in text
    assert "确认重置 EPI wiki" in text
    assert "确认同时重置 EPI config" in text
    assert "wiki-reset --vault <vault> --preview --json" in text
    assert "wiki-reset --vault <vault>" in text
    assert "--reset-config-confirmed-by" in text
    assert "不需要备份" in text
    assert "do not back up wiki content" in text
    assert "Misdelete Recovery" in text
    assert "误删" in text
    assert "without the exact second confirmation" in text
    assert "wiki-repair --vault <vault> --json" in recovery
    assert "config-recover --vault <vault> --json" in recovery
    assert "config-restore --vault <vault>" in recovery
    assert "确认恢复 EPI config" in recovery
    assert "Actively ask whether the user wants help restoring important settings" in recovery
    assert "<vault-parent>\\paper-research-wiki-reset-backups\\" in recovery
    assert "backup outside the active vault" in recovery


def test_epi_skills_delegate_onboarding_wording_to_config_doc():
    for skill_name in [
        "paper-discovery",
        "paper-ingest",
        "zotero-sync",
        "skill-aware-evolve",
    ]:
        text = _read(SKILL_DIR / skill_name / "SKILL.md")

        assert "docs\\config.md" in text
        assert "config-setup" in text


def test_epi_skills_document_precise_one_to_three_prepare_ranked_path():
    discovery = _read(SKILL_DIR / "paper-discovery" / "SKILL.md")
    ingest = _read(SKILL_DIR / "paper-ingest" / "SKILL.md")
    mineru = _read(SKILL_DIR / "mineru-paper-parser" / "SKILL.md")

    assert "prepare-ranked" in discovery
    assert "--max-papers 10" in discovery
    assert "--skip-existing" in discovery
    assert "smoke test" in discovery
    assert "profile-derived" in discovery
    assert "stops after" in discovery
    assert "acquire-record.json" in discovery
    assert "parse-record.json" in discovery
    assert "--max-papers 10" in ingest
    assert "--skip-existing" in ingest
    assert "Do not use `advance-paper`, `advance-ranked`, or `advance-batch`" in ingest
    assert "Source-First Wiki Handoff" in ingest
    assert "report --run-id <run-id>" in ingest
    assert "mineru/paper.md" in ingest
    assert "mineru/images/*" in ingest
    assert "central formulas" in ingest
    assert "not the source of truth" in ingest
    assert "tex_source=markdown-fallback" in mineru
    assert "mineru-command\\paper" in mineru
    assert "mineru-command\\parsed" in mineru
    assert "MinerU reported done but produced no Markdown output" in mineru


def test_paper_discovery_skill_documents_quality_first_chat_recommendations():
    discovery = _read(SKILL_DIR / "paper-discovery" / "SKILL.md")

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
    assert "references/workflows/multi-source-discovery.md" in discovery
    assert "references/quality-gate.md" in discovery
    assert "The full EPI chain stays documented" in discovery


def test_paper_discovery_skill_defines_stronger_high_quality_search_protocol():
    discovery = _read(SKILL_DIR / "paper-discovery" / "SKILL.md")

    assert "query-planner.py" in discovery
    assert "--no-query-plan" in discovery
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
    assert "references/workflows/multi-source-discovery.md" in discovery
    assert "references/quality-gate.md" in discovery
    assert "references/output-format.md" in discovery
    assert "references/anti-patterns.md" in discovery
    assert "The full EPI chain stays documented" in discovery


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
        / "references"
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
    assert "domain_focus_terms" in search_protocol
    assert "hard anchor gate" in search_protocol
    assert "publisher PDF blocks" in search_protocol
    assert "two-stage-retrieval.md" in search_protocol
    assert "citation-graph.md" in search_protocol
    assert "paper_search_mcp" in search_protocol
    assert "source tier" in source_tiers.lower()
    assert "field community lists" in source_tiers
    assert "DOI" in dedup_engine
    assert "already_in_library:<slug>" in dedup_engine
    assert "venue_prior" in venue_prior
    assert "configured or curated prior" in venue_prior
    assert "Domain examples, not defaults" in venue_prior
    assert "Robotics/control profiles may list" in venue_prior
    assert "High Recall Candidate Pool" in two_stage
    assert "query-plan.json" in two_stage
    assert "domain_focus_terms" in two_stage
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
    assert "EPI 实测证据" in output_format
    assert "Method-only leakage" in anti_patterns


def test_paper_ingest_source_first_reading_reference_exists():
    ingest = _read(SKILL_DIR / "paper-ingest" / "SKILL.md")
    source_first = _read(SKILL_DIR / "paper-ingest" / "references" / "source-first-reading.md")

    assert "references/source-first-reading.md" in ingest
    assert "Claim Cards" in source_first
    assert "Formula And Figure Rules" in source_first
    assert "mineru/paper.tex" in source_first
    assert "mineru/images/*" in source_first
    assert "reader/claim-support.json" in source_first
