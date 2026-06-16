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

    assert manifest["version"] == "2.3.1"
    assert manifest["interface"]["shortDescription"].startswith("v2.3.1 | Paper Source:")
    assert "recommend" in manifest["interface"]["shortDescription"]
    assert "session_recommendations" in manifest["interface"]["longDescription"]
    assert "discover-papers" in manifest["interface"]["longDescription"]
    assert "Codex automation approval" in manifest["interface"]["longDescription"]
    _assert_contains_all(
        docs,
        [
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
            "discover-papers-record.json",
            "Paper Wiki",
            "final-source-review.json",
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
