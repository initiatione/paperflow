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
        "第二步，我需要知道你主要看哪类论文",
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
    assert "默认看方法/系统/实验论文，不默认看综述" in text
    assert "config-status --vault <vault> --json --include-values --include-runtime" in text


def test_config_setup_skill_owns_initialization_and_update_onboarding():
    skill_path = SKILL_DIR / "config-setup" / "SKILL.md"
    text = _read(skill_path)

    assert "name: config-setup" in text
    assert "初始化" in text
    assert "修改" in text
    assert "doctor" in text
    assert "config-status" in text
    assert "--include-values --include-runtime" in text
    assert "Only run `doctor`" in text
    assert "默认不是综述论文" in text
    assert "一次只问一个问题" in text
    assert "每个问题必须说明影响" in text
    assert "参考方向" in text
    assert "最终确认前不得运行 `init-config`" in text
    assert "最终确认前不得运行 `apply-config-update`" in text
    assert "不要一次性输出完整默认配置" in text
    assert "你刚刚选了什么" in text
    assert "runtime.json" in text
    assert "不保存 token 明文" in text


def test_wiki_setup_skill_owns_vault_initialization_and_reset_confirmation():
    text = _read(SKILL_DIR / "wiki-setup" / "SKILL.md")

    assert "name: wiki-setup" in text
    assert "scripts\\init_paper_wiki.py" in text
    assert "Initialization is idempotent" in text
    assert "Reset is destructive" in text
    assert "wiki structure reset and EPI config reset are separate operations" in text
    assert "_meta\\epi-config.yaml" in text
    assert "_meta\\epi-config-state.json" in text
    assert "_meta\\config-history\\" in text
    assert r"%USERPROFILE%\.codex\plugins\paper-search\epi\runtime.json" in text
    assert "config-status --vault <vault> --json --include-values --include-runtime" in text
    assert "确认重置 EPI wiki" in text
    assert "确认同时重置 EPI config" in text
    assert "wiki-reset --vault <vault>" in text
    assert "--reset-config-confirmed-by" in text
    assert "config-recover --vault <vault> --json" in text
    assert "config-restore --vault <vault>" in text
    assert "确认恢复 EPI config" in text
    assert "不需要备份" in text
    assert "do not back up wiki content" in text
    assert "Misdelete Recovery" in text
    assert "误删" in text
    assert "Actively ask whether the user wants help restoring important settings" in text
    assert "<vault-parent>\\paper-research-wiki-reset-backups\\" in text
    assert "backup outside the active vault" in text
    assert "without the exact second confirmation" in text


def test_epi_skills_delegate_onboarding_wording_to_config_doc():
    for skill_name in [
        "paper-discovery",
        "paper-ingest",
        "zotero-sync",
        "skill-aware-evolve",
    ]:
        text = _read(SKILL_DIR / skill_name / "SKILL.md")

        assert "docs\\config.md" in text
        assert "聊天式初始化脚本" in text
        assert "config-setup" in text
        assert "不要自由发挥成技术字段问卷" in text
        assert "不要一次性输出完整默认配置" in text


def test_epi_skills_document_precise_one_to_three_prepare_ranked_path():
    discovery = _read(SKILL_DIR / "paper-discovery" / "SKILL.md")
    ingest = _read(SKILL_DIR / "paper-ingest" / "SKILL.md")
    mineru = _read(SKILL_DIR / "mineru-paper-parser" / "SKILL.md")

    assert "prepare-ranked" in discovery
    assert "stops after" in discovery
    assert "acquire-record.json" in discovery
    assert "parse-record.json" in discovery
    assert "Do not use `advance-paper`, `advance-ranked`, or `advance-batch`" in ingest
    assert "tex_source=markdown-fallback" in mineru
    assert "mineru-command\\paper" in mineru
    assert "mineru-command\\parsed" in mineru


def test_paper_discovery_skill_documents_quality_first_chat_recommendations():
    discovery = _read(SKILL_DIR / "paper-discovery" / "SKILL.md")

    assert "references/output-format.md" in discovery
    assert "references/search-protocol.md" in discovery
    assert "references/quality-gate.md" in discovery
    assert "The full EPI chain stays documented" in discovery


def test_paper_discovery_skill_defines_stronger_high_quality_search_protocol():
    discovery = _read(SKILL_DIR / "paper-discovery" / "SKILL.md")

    assert "references/search-protocol.md" in discovery
    assert "references/quality-gate.md" in discovery
    assert "references/output-format.md" in discovery
    assert "The full EPI chain stays documented" in discovery


def test_paper_discovery_reference_files_exist_and_hold_split_protocol():
    search_protocol = _read(SKILL_DIR / "paper-discovery" / "references" / "search-protocol.md")
    quality_gate = _read(SKILL_DIR / "paper-discovery" / "references" / "quality-gate.md")
    output_format = _read(SKILL_DIR / "paper-discovery" / "references" / "output-format.md")

    assert "3-5 query variants" in search_protocol
    assert "paper_search_mcp" in search_protocol
    assert "Tier A" in quality_gate
    assert "recall gap" in quality_gate
    assert "推荐优先看" in output_format
    assert "EPI 实测证据" in output_format
