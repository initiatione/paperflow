from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parents[1]
SKILLS = ROOT / "skills"
CHINESE_TEXT = re.compile(r"[\u4e00-\u9fff]")
CATEGORIES = {"primary", "support", "maintenance"}
MAX_ENTRYPOINT_LINES = 90
WORKFLOW_SKILLS = {
    "paper-discovery",
    "paper-ingest",
    "epi-paper-deposition",
    "wiki-setup",
}


def _safe_load_yaml(text):
    try:
        import yaml
    except ModuleNotFoundError:
        return None

    return yaml.safe_load(text)


def _load_routing():
    text = (SKILLS / "routing.yaml").read_text(encoding="utf-8")
    loaded = _safe_load_yaml(text)
    if loaded is not None:
        return loaded

    routes = {}
    current = None
    current_key = None
    in_routes = False

    for line in text.splitlines():
        if line == "routes:":
            in_routes = True
            continue
        if line == "task_closure:":
            break
        if not in_routes or not line.strip():
            continue

        route_match = re.match(r"^  ([a-z0-9_]+):$", line)
        if route_match:
            current = {}
            routes[route_match.group(1)] = current
            current_key = None
            continue

        key_match = re.match(r"^    ([a-z_]+):\s*(.*)$", line)
        if key_match and current is not None:
            key, value = key_match.groups()
            current_key = key
            if value:
                current[key] = value
            elif key == "triggers":
                current[key] = []
            continue

        list_match = re.match(r"^      -\s+(.*)$", line)
        if list_match and current is not None and current_key:
            current.setdefault(current_key, []).append(list_match.group(1))

    return {"routes": routes}


def _routes_by_skill():
    routes = _load_routing()["routes"]
    by_skill = {}

    for route_name, route in routes.items():
        skill = route.get("skill")
        assert skill, route_name
        assert skill.endswith("/SKILL.md"), route_name
        skill_name = skill.removesuffix("/SKILL.md")
        assert skill_name not in by_skill, skill_name
        by_skill[skill_name] = route

    return by_skill


def _load_skill_frontmatter(skill_path):
    text = skill_path.read_text(encoding="utf-8")
    match = re.search(r"(?s)^---\s*(.*?)\s*---", text)
    assert match, skill_path

    loaded = _safe_load_yaml(match.group(1))
    if loaded is not None:
        return loaded

    frontmatter = {}
    lines = match.group(1).splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        scalar = re.match(r"^([a-z_]+):\s*(.*)$", line)
        if not scalar:
            index += 1
            continue
        key, value = scalar.groups()
        if value == ">":
            folded = []
            index += 1
            while index < len(lines) and lines[index].startswith("  "):
                folded.append(lines[index].strip())
                index += 1
            frontmatter[key] = " ".join(folded)
            continue
        frontmatter[key] = value.strip('"')
        index += 1

    return frontmatter


def _load_openai_metadata(metadata_path):
    text = metadata_path.read_text(encoding="utf-8")
    loaded = _safe_load_yaml(text)
    if loaded is not None:
        return loaded

    interface = {}
    for line in text.splitlines():
        match = re.match(r'^\s{2}([a-z_]+):\s+"([^"]*)"$', line)
        if match:
            key, value = match.groups()
            interface[key] = value

    return {"interface": interface}


def test_skill_bundle_has_the_expected_entrypoints():
    expected = [
        "config-setup",
        "epi-paper-deposition",
        "mineru-paper-parser",
        "paper-discovery",
        "paper-ingest",
        "run-lifecycle",
        "skill-aware-evolve",
        "topic-tracking",
        "wiki-provenance",
        "wiki-setup",
        "zotero-sync",
    ]

    for skill_name in expected:
        skill_path = SKILLS / skill_name / "SKILL.md"
        assert skill_path.exists(), skill_name


def test_all_skills_are_classified_in_plugin_routing():
    actual_skills = {
        path.name
        for path in SKILLS.iterdir()
        if path.is_dir() and (path / "SKILL.md").exists()
    }
    route_blocks = _routes_by_skill()

    assert set(route_blocks) == actual_skills

    for skill_name in actual_skills:
        route = route_blocks.get(skill_name)
        assert route, f"missing route block for {skill_name}"
        assert route.get("category") in CATEGORIES, skill_name
        assert isinstance(route.get("triggers"), list), skill_name
        assert route["triggers"], skill_name


def test_core_skill_entrypoints_route_to_workflows_without_becoming_runbooks():
    route_blocks = _routes_by_skill()

    for skill_name in WORKFLOW_SKILLS:
        skill_path = SKILLS / skill_name / "SKILL.md"
        entrypoint = skill_path.read_text(encoding="utf-8")
        entrypoint_lines = entrypoint.splitlines()
        assert len(entrypoint_lines) <= MAX_ENTRYPOINT_LINES, skill_name
        assert "Workflow Routing" in entrypoint, skill_name

        workflows = route_blocks[skill_name].get("workflows", [])
        assert workflows, skill_name
        for workflow in workflows:
            workflow_path = SKILLS / workflow
            assert workflow_path.exists(), workflow
            assert workflow_path.read_text(encoding="utf-8").strip(), workflow

    routed_workflows = {
        str(SKILLS / workflow)
        for route in route_blocks.values()
        for workflow in route.get("workflows", [])
    }
    actual_workflows = {
        str(path)
        for path in SKILLS.glob("*/workflows/*.md")
    }
    assert actual_workflows == routed_workflows


def test_skill_descriptions_and_routes_include_chinese_task_triggers():
    route_blocks = _routes_by_skill()

    for skill_dir in SKILLS.iterdir():
        if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").exists():
            continue

        frontmatter = _load_skill_frontmatter(skill_dir / "SKILL.md")
        description = frontmatter.get("description", "")
        assert CHINESE_TEXT.search(description), skill_dir.name

        route = route_blocks.get(skill_dir.name)
        assert route, skill_dir.name
        assert any(CHINESE_TEXT.search(str(trigger)) for trigger in route.get("triggers", [])), skill_dir.name


def test_skill_ui_metadata_exists_for_each_skill():
    for skill_dir in SKILLS.iterdir():
        if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").exists():
            continue
        metadata_path = skill_dir / "agents" / "openai.yaml"
        assert metadata_path.exists(), skill_dir.name

        metadata = _load_openai_metadata(metadata_path)
        interface = metadata.get("interface", {})
        assert interface.get("display_name"), skill_dir.name
        short_description = interface.get("short_description", "")
        assert 25 <= len(short_description) <= 64, skill_dir.name
        default_prompt = interface.get("default_prompt", "")
        assert f"${skill_dir.name}" in default_prompt, skill_dir.name


def test_skill_bundle_excludes_tracked_python_cache_artifacts_and_gitignore_covers_cache():
    result = subprocess.run(
        ["git", "ls-files", "plugins/epi/skills"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    cache_artifacts = [
        path
        for path in result.stdout.splitlines()
        if "__pycache__" in Path(path).parts or path.endswith(".pyc")
    ]

    assert cache_artifacts == []

    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "__pycache__/" in gitignore
    assert "*.py[cod]" in gitignore


def test_paper_discovery_keeps_policy_in_skill_and_references():
    discovery = (SKILLS / "paper-discovery" / "SKILL.md").read_text(encoding="utf-8")

    assert "references/query-planner.md" in discovery
    assert "references/search-protocol.md" in discovery
    assert not (SKILLS / "paper-discovery" / "README.md").exists()


def test_epi_paper_deposition_documents_required_wiki_adapter_stack():
    deposition = (SKILLS / "epi-paper-deposition" / "SKILL.md").read_text(encoding="utf-8")
    formal_workflow = (
        SKILLS / "epi-paper-deposition" / "workflows" / "formal-wiki-write.md"
    ).read_text(encoding="utf-8")
    combined = "\n".join([deposition, formal_workflow])

    assert "workflows/formal-wiki-write.md" in deposition
    assert "wiki_deposition_task.json" in combined
    assert "epi-wiki-deposition" in deposition
    for skill in [
        "llm-wiki",
        "wiki-ingest",
        "wiki-context-pack",
        "wiki-lint",
        "wiki-stage-commit",
        "wiki-status",
        "wiki-query",
        "wiki-provenance",
        "tag-taxonomy",
    ]:
        assert skill in combined
    for field in [
        "title",
        "category",
        "page_family",
        "sources",
        "summary",
        "provenance",
        "base_confidence",
        "lifecycle",
        "tier",
    ]:
        assert field in combined
    assert "draft` or `review-needed`" in combined
    assert "must not enter the formal graph" in combined
