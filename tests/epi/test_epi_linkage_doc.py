from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LINKAGE_DOC = ROOT / "plugins" / "epi" / "docs" / "epi-linkage.md"


def test_epi_linkage_doc_defines_scope_pipeline_and_sync_rule():
    text = LINKAGE_DOC.read_text(encoding="utf-8")

    assert "# EPI 插件链路说明" in text
    assert "高质量论文收集" in text
    assert "LLM Wiki" in text
    assert "轻阅读负担的阅读报告" in text
    assert "不是从 0 到完成投稿的自动科研工作台" in text
    assert "每次修改或优化 EPI 插件" in text
    assert "必须同步更新本文档" in text
    assert "默认 fast-ingest" in text
    assert "reviewed-ingest" in text
    assert "audited-ingest" in text
    assert "stops_after=source-staging" in text
    assert "SkillOpt" in text
    assert "EmbodiSkill" in text
    assert "execution_lapse" in text
    assert "_epi/evolution/pending" in text
    assert "_epi/evolution/rejected" in text
    assert "action_required" in text
    assert "configuration_change 必须 record-only" in text
    assert "metric" in text
    assert "operator" in text
    assert "passed=true" in text
    assert "propose-config-update" in text
    assert "证据强度与可信状态" in text
    assert "wiki-ingest-brief.json" in text
    assert "canonical EPI-to-PRW handoff" in text
    assert "wiki_deposition_task.json is legacy" in text
    assert "Wiki 沉淀价值" in text
    assert "wiki-ingest agent" in text
    assert "Claude" in text
    assert "Codex" in text
    assert "Ar9av/obsidian-wiki" in text
    assert "kepano/obsidian-skills" in text
    assert "initiatione/obsidian-wiki-dev" in text
    assert "obsidian-wiki-dev" in text
    assert "vault contract" in text
    assert "不决定最终 wiki 页面" in text
    assert "Obsidian Wiki 规则来源模型" in text
    assert "不能把 Obsidian Wiki 写入规则简化成" in text
    assert "wiki_rule_source_model" in text
    assert "wiki-ingest-handoff" in text
    assert "record-wiki-ingest" in text
    assert "wiki-ingest-record.json" in text
    assert "wiki_ingest_recorded" in text
    assert "resolution_order" in text
    assert "must_read_before_final_write" in text
    assert "write_contract_requirements" in text
    assert "本地 helper/adapters" in text
    assert "external wiki skills are optional helpers" in text
    assert "Markdown vault 是 source of truth" in text
    assert "只读 handoff 渲染器" in text
    assert "agent checklist" in text


def test_epi_linkage_doc_matches_current_dry_run_artifact_names():
    text = LINKAGE_DOC.read_text(encoding="utf-8")

    assert "_epi/runs/<run-id>/normalized.json" in text
    assert "_epi/runs/<run-id>/rank.json" in text
    assert "_epi/runs/<run-id>/candidates.normalized.json" not in text
    assert "_epi/runs/<run-id>/candidates.ranked.json" not in text


def test_epi_linkage_documents_review_sessions_and_evidence_index():
    text = LINKAGE_DOC.read_text(encoding="utf-8")
    assert "_epi/reviews/<review-id>/" in text
    assert "candidates.json" in text
    assert "shortlist.json" in text
    assert "fetch_plan.json" in text
    assert "coverage.json" in text
    assert "_epi/raw/<slug>/evidence-index.json" in text
    assert "_epi/meta/evidence-index.json" in text
