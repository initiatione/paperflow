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
        assert "不要自由发挥成技术字段问卷" in text
