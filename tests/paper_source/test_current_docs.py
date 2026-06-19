import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT / "plugins" / "paper-source"
WIKI_ROOT = ROOT / "plugins" / "paper-wiki"
DOCS = SOURCE_ROOT / "docs"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _source_doc(name: str) -> str:
    return _read(DOCS / name)


def _assert_contains_all(text: str, phrases: list[str]) -> None:
    missing = [phrase for phrase in phrases if phrase not in text]
    assert not missing, "missing required doc phrases: " + ", ".join(missing)


def _assert_contains_none(text: str, phrases: list[str]) -> None:
    present = [phrase for phrase in phrases if phrase in text]
    assert not present, "unexpected retired doc phrases: " + ", ".join(present)


def test_paper_source_manifest_version_and_public_description_are_synced():
    manifest = json.loads(_read(SOURCE_ROOT / ".codex-plugin" / "plugin.json"))
    docs = "\n".join(_source_doc(name) for name in ["CHANGELOG.md", "paper-source-linkage.md", "structure.md"])

    assert manifest["version"] == "2.8.2"
    assert manifest["interface"]["shortDescription"].startswith("v2.8.2 | Paper Source:")
    assert "health doctor" in manifest["interface"]["shortDescription"]
    assert "MCP/runtime diagnostics" in manifest["interface"]["shortDescription"]
    assert "graph visibility" in manifest["interface"]["shortDescription"]
    assert "config diagnostics" in manifest["interface"]["shortDescription"]
    assert "CJK query planning" in manifest["interface"]["shortDescription"]
    assert "progress telemetry" in manifest["interface"]["shortDescription"]
    assert "recommend" in manifest["interface"]["shortDescription"]
    assert "benchmark gates" in manifest["interface"]["shortDescription"]
    assert "Grok diagnostics" in manifest["interface"]["shortDescription"]
    assert "required concept groups" in manifest["interface"]["shortDescription"]
    assert "recall/risk checks" in manifest["interface"]["shortDescription"]
    assert "session_recommendations" in manifest["interface"]["longDescription"]
    assert "progress-events.jsonl" in manifest["interface"]["longDescription"]
    assert "progress-summary.json" in manifest["interface"]["longDescription"]
    assert "report.json.discovery_context.discovery_progress" in manifest["interface"]["longDescription"]
    assert "empty graph.json search plus app.json userIgnoreFilters" in manifest["interface"]["longDescription"]
    assert "required concept groups" in manifest["interface"]["longDescription"]
    assert "CJK topic terms" in manifest["interface"]["longDescription"]
    assert "strict year parsing" in manifest["interface"]["longDescription"]
    assert "shared timeout budgets" in manifest["interface"]["longDescription"]
    assert "required-concept-group" in manifest["interface"]["longDescription"]
    assert "discovery-benchmark gates" in manifest["interface"]["longDescription"]
    assert "precision/recall/review-leakage/duplicate/citation/config regressions" in manifest["interface"]["longDescription"]
    assert "term_provenance_detail" in manifest["interface"]["longDescription"]
    assert "query-plan diagnostics" in manifest["interface"]["longDescription"]
    assert "acronym or synonym expansions" in manifest["interface"]["longDescription"]
    assert "lexical relevance checks" in manifest["interface"]["longDescription"]
    assert "normalized citation ranking" in manifest["interface"]["longDescription"]
    assert "config/agent-plan quality-evidence lexicons" in manifest["interface"]["longDescription"]
    assert "provider-supplied official versions or related papers" in manifest["interface"]["longDescription"]
    assert "provider quality-risk checks" in manifest["interface"]["longDescription"]
    assert "identity/relevance/inspectability/validation/source-confidence/reproducibility/request-risk/quality-risk dimensions" in manifest["interface"]["longDescription"]
    assert "retrieval and metadata coverage rather than a semantic quality ranker" in manifest["interface"]["longDescription"]
    assert "non-Reject session_recommendations" in manifest["interface"]["longDescription"]
    assert "discover-papers" in manifest["interface"]["longDescription"]
    assert "grok-search-rs MCP" in manifest["interface"]["longDescription"]
    assert "plugin-installed grok-search-rs MCP self-registration" in manifest["interface"]["longDescription"]
    assert "high-quality supplemental recall" in manifest["interface"]["longDescription"]
    assert "retry outcomes" in manifest["interface"]["longDescription"]
    assert "filter/rank non-contribution counts" in manifest["interface"]["longDescription"]
    assert "Codex automation approval" in manifest["interface"]["longDescription"]
    _assert_contains_all(
        docs,
        [
            "Paper Source 2.8.2",
            "Paper Wiki 1.1.0",
            "paper-wiki-zotero-sync-report-v1",
            "Paper Wiki 1.0.6",
            "official Zotero helper adapters",
            "Paper Source 2.8.1",
            "Paper Wiki 1.0.5",
            "graph.json",
            "userIgnoreFilters",
            "Paper Source 2.8.0",
            "unknown_keys",
            "Paper Source 2.7.1",
            "timeout_budget_exhausted",
            "CJK runs",
            "strict leading 19xx/20xx year",
            "Paper Source 2.7.0",
            "paper-source-progress-events-v1",
            "progress-events.jsonl",
            "progress-summary.json",
            "report.json.discovery_context.discovery_progress",
            "Paper Source 2.6.0",
            "paper-source-required-concept-groups-v1",
            "required_concept_group_mismatch",
            "required_concept_group_rejects",
            "Paper Source 2.5.3",
            "Paper Source 2.5.2",
            "Paper Source 2.5.0",
            "Paper Source 2.4.0",
            "Paper Source 2.3.14",
            "Paper Source 2.3.13",
            "Paper Source 2.3.12",
            "Paper Source 2.3.10",
            "term_provenance_detail",
            "paper-source-query-plan-diagnostics-v1",
            "acronym_expansions",
            "token-boundary lexical matching",
            "discovery-benchmark",
            "paper-source-discovery-benchmark-cases-v1",
            "paper-source-benchmark-v1",
            "paper-source-recall-gap-record-v1",
            "paper-source-quality-risk-record-v1",
            "paper-source-recall-expansion-v1",
            "quality-risk-record.json",
            "recall-gap-record.json",
            "quality_gate.dimensions.quality_risk",
            "verified_quality_risk",
            "publication-age-normalized citation quality",
            "Quality-evidence lexicons",
            "Missing citation/venue evidence",
            "Paper Source 2.3.7",
            "Paper Source 2.3.8",
            "Paper Source 2.3.6",
            "Paper Source 2.3.5",
            "quality_gate.dimensions",
            "positive_keywords_saturated",
            "semantic quality gate",
            "keyword_coverage_score",
            "quality_reject_debug",
            "no_primary_recommendations_summary",
            "hard domain anchors",
            "non-Reject",
            "Paper Source 2.3.4",
            "missing_required_doi",
            "doi_recovery_summary",
            "doi_resolution_summary",
            "PAPER_SOURCE_GROK_MODEL_FALLBACKS",
            "existing_library_appendix",
            "raw_scan_policy",
            "唯一 canonical backlog",
            "reference-index 缺失/不可用",
            "verification_summary",
            "per-item verification warnings",
            "citation_count_source/status",
            "grok-search-rs MCP",
            "Grok-only",
            "库中已有，可回看",
            "禁止把多个已入库题名压成一行分号分隔列表",
            "Paper Source 2.3.2",
            "Paper Source 2.3.0",
            "Paper Source 2.3.1",
            "PAPER_SOURCE_MINERU_CDN_RESOLVE",
            "download_recovery",
            "Paper Source 2.2.0",
            "Paper Source 2.2.1",
            "Paper Source 2.1.1",
            "Paper Source 2.1.0",
            "Paper Source 2.0.0",
            "discover-papers",
            "discover-papers-record.json",
            "wiki-ingest-brief.json",
            "record-human-approval",
            "codex-automation:<task-id>",
            "automation_handoff",
            "wiki-ingest-trigger",
            "record-wiki-ingest",
            "session_recommendations",
            "paper-source-session-recommendations-v1",
            "paper-source-auto-staging-plan-v1",
            "marketplace refresh / reinstall / installed-cache verification remain",
        ],
    )


def test_plugin_development_rules_keep_version_docs_and_runtime_validation_contracts():
    combined = "\n".join(
        [
            _read(ROOT / "README.md"),
            _read(ROOT / "AGENTS.md"),
            _read(ROOT / "docs" / "plugin-development.md"),
            _read(SOURCE_ROOT / "AGENTS.md"),
            _read(WIKI_ROOT / "AGENTS.md"),
        ]
    )

    _assert_contains_all(
        combined,
        [
            "docs/plugin-development.md",
            "任何插件改动都必须同步版本信息",
            "plugins/<plugin>/.codex-plugin/plugin.json",
            "interface.shortDescription",
            "PaperFlow",
            "Paper Source",
            "Paper Wiki",
            "PS/PW 是允许的自然语言别名和触发短语",
            "本地合同和测试优先于外部参考",
            "源码验证通过不等于用户运行态已更新",
            "installed runtime validation",
            "git diff --check",
        ],
    )


def test_structure_doc_covers_current_slimmed_modules_and_boundaries():
    text = _source_doc("structure.md")

    _assert_contains_all(
        text,
        [
            "scripts/build/paper_source/",
            "orchestrator_discovery.py",
            "orchestrator_repair.py",
            "query_plan_build.py",
            "stage_wiki_brief.py",
            "frontmatter.py",
            "review/",
            "recommendation_output.py",
            "auto_staging.py",
            "discover_papers.py",
            "discovery_benchmark.py",
            "quality_risk_recall.py",
            "wiki_ingest_record.py",
            "wiki_query.py",
            "runtime_config.py",
            "paper_source_repository.py",
            "旧 `epi_repository.py` shim",
            "Paper Source 2.0.0",
            "wiki-ingest-brief.json",
            "Paper Wiki `$paper-research-wiki`",
            "不要把安装 cache 当成开发源",
        ],
    )


def test_workflow_and_linkage_docs_cover_kept_runtime_pipeline():
    combined = "\n".join(
        [
            _source_doc("workflow.md"),
            _source_doc("paper-source-linkage.md"),
            _source_doc("progress.md"),
            _source_doc("evaluation.md"),
        ]
    )

    _assert_contains_all(
        combined,
        [
            "dry-run",
            "discover-papers",
            "prepare-ranked",
            "paper-gate",
            "wiki-ingest-handoff",
            "record-human-approval",
            "Codex automation",
            "codex-automation:<task-id>",
            "automation_handoff",
            "普通 `discover-papers`",
            "wiki-ingest-trigger",
            "record-wiki-ingest",
            "zotero-sync",
            "report.json",
            "run-state.json",
            "默认 fast-ingest",
            "reviewed-ingest",
            "audited-ingest",
            "source-staging",
            "_paper_source/reviews",
            "_paper_source/meta/evidence-index.json",
            "session_recommendations",
            "auto_staging_plan",
            "discovery-benchmark",
            "paper-source-discovery-benchmark-cases-v1",
            "paper-source-benchmark-v1",
            "recall-gap-record.json",
            "quality-risk-record.json",
            "discover-papers-record.json",
            "Paper Wiki",
            "final-source-review.json",
            "grok-search-rs MCP",
            "targeted",
            "parallel",
        ],
    )


def test_docs_do_not_reintroduce_retired_user_entrypoints():
    active_docs = "\n".join(
        _source_doc(name)
        for name in [
            "paper-source-linkage.md",
            "structure.md",
            "workflow.md",
            "progress.md",
        ]
    )

    _assert_contains_none(
        active_docs,
        [
            "rollback-promotion",
            "promote_to_wiki.py` 是",
            "epi_repository.py` 是内部迁移 shim",
            "migrate_active_internal_artifacts.py` 是",
        ],
    )
