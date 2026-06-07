from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parents[1]
SKILLS = ROOT / "skills"
BUILD_ROOT = ROOT / "scripts" / "build"
if str(BUILD_ROOT) not in sys.path:
    sys.path.insert(0, str(BUILD_ROOT))
CHINESE_TEXT = re.compile(r"[\u4e00-\u9fff]")
CATEGORIES = {"primary", "support", "maintenance", "compatibility"}
MAX_ENTRYPOINT_LINES = 90
MAX_DESCRIPTION_LINES = 25
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
    data = {"routes": routes, "always_read": []}
    current = None
    current_key = None
    in_routes = False
    in_always_read = False

    for line in text.splitlines():
        top_key = re.match(r"^([a-z_]+):\s*(.*)$", line)
        if top_key and not line.startswith(" "):
            key, value = top_key.groups()
            if key in {"schema_version", "source_of_truth"}:
                data[key] = value
            in_always_read = key == "always_read"
            if key == "routes":
                in_routes = True
                in_always_read = False
                continue
        if in_always_read:
            always_match = re.match(r"^  -\s+(.*)$", line)
            if always_match:
                data["always_read"].append(always_match.group(1))
            continue
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

    return data


def _skill_line_counts(skill_path):
    lines = skill_path.read_text(encoding="utf-8").splitlines()
    description_lines = 0
    body_start = 0
    if lines and lines[0] == "---":
        end = None
        for index, line in enumerate(lines[1:], start=1):
            if line == "---":
                end = index
                break
        if end is not None:
            in_description = False
            for line in lines[1:end]:
                if line.startswith("description:"):
                    in_description = True
                    description_lines += 1
                    continue
                if in_description:
                    if re.match(r"^\S", line):
                        in_description = False
                    else:
                        description_lines += 1
            body_start = end + 1
    return {
        "description": description_lines,
        "body": len(lines[body_start:]),
    }


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


def test_plugin_routing_manifest_is_the_small_source_of_truth():
    routing = _load_routing()

    assert routing["schema_version"] == "epi-skill-routing-v1"
    assert routing["source_of_truth"] == "skills/routing.yaml"
    assert len(routing["always_read"]) <= 3


def test_epi_repository_initialization_uses_lean_default_structure(tmp_path):
    from epi.epi_repository import ensure_epi_repository

    ensure_epi_repository(tmp_path)

    required = [
        "_epi/README.md",
        "_epi/manifest.json",
        "_epi/raw",
        "_epi/staging/papers",
        "_epi/staging/wiki-batches/pending",
        "_epi/meta/config-history",
        "_epi/meta/formal-page-snapshots",
        "_epi/policies/retention.json",
    ]
    for relative in required:
        assert (tmp_path / relative).exists(), relative

    on_demand = [
        "_epi/runs",
        "_epi/quarantine",
        "_epi/evolution",
        "_epi/cache",
        "_epi/tmp",
        "_epi/tmp-manual-pdfs",
    ]
    for relative in on_demand:
        assert not (tmp_path / relative).exists(), relative

    manifest = (tmp_path / "_epi" / "manifest.json").read_text(encoding="utf-8")
    assert "core_sections" in manifest
    assert "on_demand_sections" in manifest
    assert "not precreated" in manifest


def test_wiki_setup_documents_lean_epi_bootstrap_contract():
    wiki_setup = (SKILLS / "wiki-setup" / "SKILL.md").read_text(encoding="utf-8")

    assert "core `_epi` bootstrap" in wiki_setup
    assert "raw/staging/meta/policies" in wiki_setup
    assert "on-demand" in wiki_setup
    assert "quarantine/evolution" in wiki_setup
    assert "raw/staging/runs/quarantine/evolution/meta roots" not in wiki_setup


def test_prw_documents_core_epi_bootstrap_without_requiring_on_demand_dirs():
    prw_root = ROOT.parent / "PRW"
    files = [
        prw_root / "skills" / "paper-research-wiki" / "SKILL.md",
        prw_root / "docs" / "workflow.md",
        prw_root / "docs" / "epi-integration.md",
        prw_root / "skills" / "paper-research-wiki" / "workflows" / "check-wiki.md",
        prw_root / "skills" / "paper-research-wiki" / "workflows" / "extract-papers.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)

    for required in ["_epi/raw/", "_epi/staging/", "_epi/meta/", "_epi/policies/"]:
        assert required in combined
    assert "not a bootstrap failure" in combined
    assert "on-demand" in combined


def test_all_skill_entrypoints_stay_thin():
    for skill_dir in SKILLS.iterdir():
        if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").exists():
            continue

        counts = _skill_line_counts(skill_dir / "SKILL.md")
        assert counts["description"] <= MAX_DESCRIPTION_LINES, skill_dir.name
        assert counts["body"] <= MAX_ENTRYPOINT_LINES, skill_dir.name


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


def test_workflows_do_not_hide_under_references():
    hidden_workflows = sorted(SKILLS.glob("*/references/workflows/*.md"))
    assert hidden_workflows == []


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
    assert "workflows/multi-source-discovery.md" in discovery
    assert "references/workflows/" not in discovery
    assert not (SKILLS / "paper-discovery" / "README.md").exists()


def test_epi_paper_deposition_is_thin_legacy_adapter():
    deposition = (SKILLS / "epi-paper-deposition" / "SKILL.md").read_text(encoding="utf-8")
    formal_workflow = (
        SKILLS / "epi-paper-deposition" / "workflows" / "formal-wiki-write.md"
    ).read_text(encoding="utf-8")
    combined = "\n".join([deposition, formal_workflow])

    assert "workflows/formal-wiki-write.md" in deposition
    assert "wiki-ingest-brief.json" in combined
    assert "legacy `wiki_deposition_task.json`" in combined
    assert "epi-wiki-deposition" in deposition
    assert "$paper-research-wiki" in combined
    assert "compatibility adapter" in combined
    assert "llm-wiki" not in combined
    assert "wiki-stage-commit" not in combined
    assert "Required frontmatter fields" not in combined
    assert "must not enter the formal graph" in combined


def test_epi_wiki_boundary_skill_docs_are_brief_first():
    files = [
        SKILLS / "paper-ingest" / "SKILL.md",
        SKILLS / "paper-ingest" / "workflows" / "approval-and-trigger.md",
        SKILLS / "wiki-setup" / "SKILL.md",
        SKILLS / "wiki-provenance" / "SKILL.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)

    for phrase in [
        "wiki-ingest-brief.json",
        "canonical EPI-to-PRW handoff",
        "wiki_deposition_task.json is legacy",
        "paper-research-wiki",
        "epi-paper-deposition",
        "external wiki skills are optional helpers",
        "record-wiki-ingest",
        "final-source-review.json",
    ]:
        assert phrase in combined


def test_prw_qmd_boundary_is_explicit_in_plugin_contracts():
    files = [
        ROOT / "docs" / "workflow.md",
        ROOT / "docs" / "epi-linkage.md",
        ROOT / "docs" / "structure.md",
        SKILLS / "epi-paper-deposition" / "SKILL.md",
        SKILLS / "epi-paper-deposition" / "workflows" / "formal-wiki-write.md",
        ROOT / "scripts" / "build" / "epi" / "wiki_contracts.py",
        ROOT / "scripts" / "build" / "epi" / "wiki_init.py",
        ROOT / "scripts" / "build" / "epi" / "stage_wiki.py",
        ROOT / "scripts" / "build" / "epi" / "wiki_ingest_handoff.py",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)

    assert "QMD" in combined
    assert "qmd collection" in combined
    for allowed in [
        "references/",
        "concepts/",
        "derivations/",
        "experiments/",
        "synthesis/",
        "reports/",
        "opportunities/",
        "AGENTS.md",
        "index.md",
        "hot.md",
        "log.md",
        "_meta/",
    ]:
        assert allowed in combined
    for ignored in [
        "_epi/**",
        "_epi/meta/formal-page-snapshots/",
        "MinerU source Markdown",
        ".obsidian/**",
        ".claude/**",
    ]:
        assert ignored in combined


def test_epi_formal_deposition_route_is_compatibility_adapter():
    routing = _load_routing()
    routes = routing["routes"]

    assert routes["wiki_setup"]["category"] == "primary"

    deposition = routes["epi_paper_deposition"]
    assert deposition["category"] == "compatibility"
    assert deposition["skill"] == "epi-paper-deposition/SKILL.md"
    assert "$paper-research-wiki" in "\n".join(deposition.get("notes", []))
