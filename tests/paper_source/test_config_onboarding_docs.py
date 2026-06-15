from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT / "plugins" / "paper-source"
CONFIG_DOC = SOURCE_ROOT / "docs" / "config.md"
SKILL_DIR = SOURCE_ROOT / "skills"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _assert_contains_all(text: str, phrases: list[str]) -> None:
    missing = [phrase for phrase in phrases if phrase not in text]
    assert not missing, "missing required onboarding phrases: " + ", ".join(missing)


def test_config_doc_preserves_plain_chinese_onboarding_contract():
    text = _read(CONFIG_DOC)

    _assert_contains_all(
        text,
        [
            "## 聊天式初始化脚本",
            "不要直接运行论文流程",
            "不懂可以直接回复：默认",
            "一次只问一个问题",
            "最终确认前不得运行 `init-config`",
            "第一步，先定论文库放哪里",
            "第二步，我需要知道你的研究画像",
            "第三步，告诉我哪些词算有用，哪些词要避开",
            "第四步，先定搜索从哪里来",
            "第五步，定每次先看多少篇",
            "第六步，MinerU 先怎么接",
            "第七步，Zotero 要不要先连",
            "最后一步，什么时候需要你确认",
            "runtime.json 不保存 token 明文",
            "Paper Source 是通用插件，不默认任何学科",
            "config-status --vault <vault> --json --include-values --include-runtime",
        ],
    )


def test_config_and_wiki_setup_skills_keep_safety_confirmations_and_doc_links():
    config_setup = _read(SKILL_DIR / "config-setup" / "SKILL.md")
    wiki_setup = _read(SKILL_DIR / "wiki-setup" / "SKILL.md")
    reset_workflow = _read(SKILL_DIR / "wiki-setup" / "workflows" / "reset-repair.md")
    recovery = _read(SKILL_DIR / "wiki-setup" / "references" / "reset-recovery.md")
    combined = "\n".join([config_setup, wiki_setup, reset_workflow, recovery])

    _assert_contains_all(
        combined,
        [
            "docs\\config.md",
            "doctor",
            "config-status",
            "--include-values --include-runtime",
            "最终确认前不得运行 `init-config`",
            "最终确认前不得运行 `apply-config-update`",
            "git init",
            "does not create a first commit",
            "Reset is destructive",
            "确认重置 Paper Source wiki",
            "确认同时重置 Paper Source config",
            "wiki-reset --vault <vault> --preview --json",
            "wiki-repair --vault <vault> --json",
            "config-recover --vault <vault> --json",
            "paper-source-repository-migrate --vault <vault> --preview --json",
            "paper-source-repository-cleanup --vault <vault> --preview --json",
        ],
    )


def test_discovery_ingest_and_mineru_skills_keep_source_first_runtime_contracts():
    discovery = _read(SKILL_DIR / "paper-discovery" / "SKILL.md")
    discovery_workflow = _read(SKILL_DIR / "paper-discovery" / "workflows" / "run-discovery.md")
    ingest = _read(SKILL_DIR / "paper-ingest" / "SKILL.md")
    prepare = _read(SKILL_DIR / "paper-ingest" / "workflows" / "prepare-ranked.md")
    approval = _read(SKILL_DIR / "paper-ingest" / "workflows" / "approval-and-trigger.md")
    mineru = _read(SKILL_DIR / "mineru-paper-parser" / "SKILL.md")
    combined = "\n".join([discovery, discovery_workflow, ingest, prepare, approval, mineru])

    _assert_contains_all(
        combined,
        [
            "references/query-planner.md",
            "references/mode-routing.md",
            "references/paper-type-taxonomy.md",
            "references/ranking-rubric.md",
            "references/source-tiers.md",
            "workflows/multi-source-discovery.md",
            "prepare-ranked",
            "--max-papers 10",
            "--skip-existing",
            "source-staging",
            "fast-ingest",
            "reviewed-ingest",
            "audited-ingest",
            "Source-First Handoff Check",
            "mineru/<slug>.md",
            "mineru/images/*",
            "formula/figure review cues",
            "not source authority",
            "MinerU reported done but produced no Markdown output",
        ],
    )


def test_support_skills_delegate_configuration_onboarding_to_config_setup():
    missing = []
    for skill_name in ["paper-discovery", "paper-ingest", "zotero-sync", "skill-aware-evolve"]:
        text = _read(SKILL_DIR / skill_name / "SKILL.md")
        if "docs\\config.md" not in text or "config-setup" not in text:
            missing.append(skill_name)
    assert not missing, "skills missing config onboarding delegation: " + ", ".join(missing)
