from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "plugins" / "epi" / "docs"


def _read(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


def test_linkage_doc_points_to_structure_progress_and_config_docs():
    text = _read("epi-linkage.md")

    assert "docs/structure.md" in text
    assert "docs/progress.md" in text
    assert "docs/config.md" in text
    assert "配套文档" in text


def test_structure_doc_covers_current_plugin_boundaries():
    text = _read("structure.md")

    assert "# EPI 插件结构说明" in text
    assert "D:\\paper-search\\plugins\\epi" in text
    assert ".codex-plugin/plugin.json" in text
    assert "scripts/build/epi/" in text
    assert "skills/" in text
    assert "config-setup" in text
    assert "paper-gate" in text
    assert "wiki-ingest-handoff" in text
    assert "agent-mediated" in text
    assert "不要把安装 cache 当成开发源" in text
    assert "runtime_config.py" in text
    assert r"C:\Users\liuchf\.codex\plugins\paper-search\epi\runtime.json" in text


def test_progress_doc_records_status_verification_and_next_steps():
    text = _read("progress.md")

    assert "# EPI 插件进度说明" in text
    assert "更新时间：2026-05-30" in text
    assert "高质量论文收集和整理" in text
    assert "config-setup" in text
    assert "paper-quality-critic" in text
    assert "wiki-ingest-handoff" in text
    assert "211 passed in 18.16s" in text
    assert "82/100" in text
    assert "waiting_for_human_gate" in text
    assert "ready_for_agent=true" in text
    assert "0.1.0+codex.20260530050337" in text
    assert "runtime.json" in text
    assert "发布前必须重跑" in text
    assert "Plugin Eval" in text
    assert "MINERU_TOKEN" in text
