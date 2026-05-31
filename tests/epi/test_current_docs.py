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
    assert "record-wiki-ingest" in text
    assert "`report`" in text
    assert "run report" in text
    assert "wiki_ingest_record.py" in text
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
    assert "更新时间：2026-06-01" in text
    assert "高质量论文收集和整理" in text
    assert "config-setup" in text
    assert "paper-quality-critic" in text
    assert "parse-quality-critic" in text
    assert "mineru/mineru-manifest.json" in text
    assert "wiki-ingest-handoff" in text
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


def test_marketplace_and_readme_describe_profile_driven_generic_epi():
    manifest = json.loads((PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    workflow = _read("workflow.md")

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

    assert "EPI 是通用论文插件，不默认任何学科方向" in workflow
    assert 'dry-run --query "<your topic>"' in workflow
    assert "prepare-ranked --run-id <run-id> --max-papers 10 --skip-existing" in workflow
    assert "prepare-ranked --run-id <run-id> --max-papers 10 --skip-existing --vault <vault> --json" in workflow
    assert "report --run-id <run-id> --vault <vault>" in workflow
    assert "report --run-id <run-id> --vault <vault> --json" in workflow
    assert "robotics embodied intelligence control" not in workflow
