from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "plugins" / "paper-source" / "skills"
ROUTING = SKILL_DIR / "routing.yaml"
RESEARCH_GRILL = SKILL_DIR / "research-grill-me"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_research_grill_route_is_primary():
    routing = _read(ROUTING)

    assert "research_grill_me:" in routing
    assert "category: primary" in routing
    assert "clarify a research direction" in routing
    assert "研究简报" in routing
    assert "skill: research-grill-me/SKILL.md" in routing
    assert "Research Briefs override Research Profile for the current task" in routing
    assert "Research Briefs cannot bypass source-staging or Paper Wiki handoff gates" in routing


def test_research_grill_skill_entrypoint_defines_questioning_contract():
    skill = _read(RESEARCH_GRILL / "SKILL.md")

    for phrase in [
        "one decision point per turn",
        "recommended answer",
        "why the decision affects Paper Source",
        "read config and repository state instead of asking",
        "no fixed round count",
        "minimum complete brief",
        "explicit user confirmation",
        "research-brief create --answers-json",
        "--vault",
        "dry-run --from-brief",
    ]:
        assert phrase in skill


def test_research_grill_outputs_general_deep_research_prompt_in_chat():
    skill = _read(RESEARCH_GRILL / "SKILL.md")
    contract = _read(RESEARCH_GRILL / "references" / "research-brief-contract.md")
    agent_metadata = _read(RESEARCH_GRILL / "agents" / "openai.yaml")
    combined = "\n".join([skill, contract, agent_metadata])

    for phrase in [
        "chat-visible general deep-research prompt",
        "deep-research prompt is companion copy",
        "### TASK",
        "### CONTEXT/BACKGROUND",
        "### SPECIFIC QUESTIONS OR SUBTASKS",
        "### KEYWORDS",
        "### CONSTRAINTS",
        "### OUTPUT FORMAT",
        "### FINAL INSTRUCTIONS",
    ]:
        assert phrase in combined


def test_research_grill_docs_preserve_paper_source_and_paper_wiki_boundaries():
    files = [
        RESEARCH_GRILL / "SKILL.md",
        RESEARCH_GRILL / "references" / "research-brief-contract.md",
        RESEARCH_GRILL / "agents" / "openai.yaml",
    ]
    combined = "\n".join(_read(path) for path in files)

    for phrase in [
        "Paper Source",
        "Paper Wiki",
        "research-brief.md",
        "agent-brief.md",
        "wiki-ingest-brief",
        "paper-search-mcp",
    ]:
        assert phrase in combined

    assert "must not write Paper Wiki formal pages directly from a Research Brief" in combined
    assert "Old EPI/PRW names are legacy-only" in combined
    assert "academic_search" not in combined
