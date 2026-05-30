from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "plugins" / "epi" / "docs"
PLUGIN_ROOT = ROOT / "plugins" / "epi"


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
    assert "<plugin-root>" in text
    assert ".codex-plugin/plugin.json" in text
    assert "scripts/build/epi/" in text
    assert "skills/" in text
    assert "config-setup" in text
    assert "paper-gate" in text
    assert "wiki-ingest-handoff" in text
    assert "agent-mediated" in text
    assert "不要把安装 cache 当成开发源" in text
    assert "runtime_config.py" in text
    assert r"%USERPROFILE%\.codex\plugins\paper-search\epi\runtime.json" in text


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
    assert "当前 `plugin.json` 中的版本" in text
    assert "runtime.json" in text
    assert "venue prior" in text
    assert "RoboWiki" in text
    assert "发布前必须重跑" in text
    assert "Plugin Eval" in text
    assert "MINERU_TOKEN" in text


def test_linkage_doc_records_paper_discovery_bundle_and_venue_prior():
    text = _read("epi-linkage.md")

    assert "nature-academic-search" in text
    assert "references/source-tiers.md" in text
    assert "references/dedup-engine.md" in text
    assert "references/venue-prior.md" in text
    assert "references/workflows/multi-source-discovery.md" in text
    assert "venue_prior" in text
    assert "verified_metrics" in text
    assert "RoboWiki" in text
    assert "知乎" in text
    assert "Ocean Engineering" in text


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
