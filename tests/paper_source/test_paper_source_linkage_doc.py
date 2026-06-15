from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LINKAGE_DOC = ROOT / "plugins" / "paper-source" / "docs" / "paper-source-linkage.md"


def _read_linkage() -> str:
    return LINKAGE_DOC.read_text(encoding="utf-8")


def _assert_contains_all(text: str, phrases: list[str]) -> None:
    missing = [phrase for phrase in phrases if phrase not in text]
    assert not missing, "missing required linkage phrases: " + ", ".join(missing)


def test_paper_source_linkage_doc_defines_scope_pipeline_and_handoff_contracts():
    text = _read_linkage()

    _assert_contains_all(
        text,
        [
            "# Paper Source",
            "高质量论文收集",
            "LLM Wiki",
            "不是从 0 到完成投稿的自动科研工作台",
            "每次修改或优化 Paper Source",
            "默认 fast-ingest",
            "reviewed-ingest",
            "audited-ingest",
            "stops_after=source-staging",
            "wiki-ingest-brief.json",
            "canonical Paper Source-to-Paper Wiki handoff",
            "wiki_deposition_task.json` is historical cleanup only",
            "wiki_rule_source_model",
            "record-wiki-ingest",
            "wiki-ingest-record.json",
            "final-source-review.json",
            "external wiki skills are optional helpers",
            "Markdown vault 是 source of truth",
            "只读 handoff 渲染器",
        ],
    )


def test_paper_source_linkage_doc_keeps_current_artifact_names_and_review_sessions():
    text = _read_linkage()

    _assert_contains_all(
        text,
        [
            "_paper_source/runs/<run-id>/normalized.json",
            "_paper_source/runs/<run-id>/rank.json",
            "_paper_source/reviews/<review-id>/",
            "candidates.json",
            "shortlist.json",
            "fetch_plan.json",
            "coverage.json",
            "_paper_source/raw/<slug>/evidence-index.json",
            "_paper_source/meta/evidence-index.json",
        ],
    )
    unexpected = [
        phrase
        for phrase in [
            "_paper_source/runs/<run-id>/candidates.normalized.json",
            "_paper_source/runs/<run-id>/candidates.ranked.json",
        ]
        if phrase in text
    ]
    assert not unexpected, "retired artifact names still documented: " + ", ".join(unexpected)
