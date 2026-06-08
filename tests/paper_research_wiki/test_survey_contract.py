from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PRW = ROOT / "plugins" / "paper-wiki"
PRW_SKILL = PRW / "skills" / "paper-research-wiki"
REFS = PRW_SKILL / "references"
SURVEY = REFS / "survey-page-anatomy.md"


def _read(path):
    assert path.exists(), f"missing {path}"
    return path.read_text(encoding="utf-8")


def test_survey_anatomy_exists_and_defines_the_survey_spine():
    text = _read(SURVEY)
    # The survey map/hub spine (validated against the AUV review exemplar).
    for section in [
        "综述定位与覆盖",
        "分类体系与逐支方法景观",
        "验证层级分布",
        "方法景观对照",
        "空白与研究机会",
        "阅读地图",
    ]:
        assert section in text, section


def test_survey_anatomy_carries_the_load_bearing_rules():
    text = _read(SURVEY)
    for rule in [
        "Borrowed-formula rule",
        "Second-hand-number rule",
        "Evidence-tier cross-cut",
        "Baseline-selection-trap",
        "Per-study evidence card",
        "evidence/literature-review",
        "method/review",
    ]:
        assert rule in text, rule
    assert "spawn" in text
    assert "derivations/" in text and "experiments/" in text


def test_survey_detection_signals_are_documented():
    text = _read(SURVEY)
    for signal in ["survey detection", "PRISMA", "no datasets were generated"]:
        assert signal in text, signal


def test_references_anatomy_gates_surveys_to_the_survey_contract():
    text = _read(REFS / "references-page-anatomy.md")
    assert "Document-type gate" in text
    assert "survey-page-anatomy.md" in text


def test_wiki_writing_standard_lists_literature_review_tier_and_points_to_survey_contract():
    text = _read(PRW / "rules" / "wiki-writing-standard.md")
    assert "literature-review" in text
    assert "survey-page-anatomy.md" in text


def test_skill_entrypoint_routes_surveys_to_the_survey_contract():
    assert "survey-page-anatomy.md" in _read(PRW_SKILL / "SKILL.md")


def test_language_gate_does_not_force_surveys_through_the_method_spine():
    text = _read(PRW / "skills" / "paper-wiki-language" / "references" / "style-guide.md")
    assert "survey-page-anatomy.md" in text
    assert "method-paper spine" in text


def test_workflows_detect_and_route_surveys():
    for workflow in ["extract-papers.md", "redo-extraction.md"]:
        text = _read(PRW_SKILL / "workflows" / workflow)
        assert "survey-page-anatomy.md" in text, workflow
