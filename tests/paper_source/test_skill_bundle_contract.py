from pathlib import Path
import re
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
ROOT = REPO_ROOT / "plugins" / "paper-source"
SKILLS = ROOT / "skills"
BUILD_ROOT = ROOT / "scripts" / "build"
if str(BUILD_ROOT) not in sys.path:
    sys.path.insert(0, str(BUILD_ROOT))
CHINESE_TEXT = re.compile(r"[\u4e00-\u9fff]")
CATEGORIES = {"primary", "support", "maintenance", "compatibility"}
MAX_ENTRYPOINT_LINES = 90
MAX_DESCRIPTION_LINES = 25
MAX_PLUGIN_SCRIPT_LINES = 2000
WORKFLOW_SKILLS = {
    "paper-discovery",
    "paper-ingest",
    "paper-source-paper-deposition",
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
        "health-doctor",
        "mineru-paper-parser",
        "paper-discovery",
        "paper-ingest",
        "paper-source-paper-deposition",
        "research-grill-me",
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

    assert routing["schema_version"] == "paper-source-skill-routing-v1"
    assert routing["source_of_truth"] == "skills/routing.yaml"
    assert len(routing["always_read"]) <= 3


def test_paper_source_repository_initialization_uses_lean_default_structure(tmp_path):
    from paper_source.paper_source_repository import ensure_paper_source_repository

    ensure_paper_source_repository(tmp_path)

    required = [
        "_paper_source/README.md",
        "_paper_source/manifest.json",
        "_paper_source/raw",
        "_paper_source/staging/papers",
        "_paper_source/staging/wiki-batches/pending",
        "_paper_source/meta/config-history",
        "_paper_source/meta/formal-page-snapshots",
        "_paper_source/policies/retention.json",
    ]
    for relative in required:
        assert (tmp_path / relative).exists(), relative

    on_demand = [
        "_paper_source/runs",
        "_paper_source/quarantine",
        "_paper_source/evolution",
        "_paper_source/cache",
        "_paper_source/tmp",
        "_paper_source/tmp-manual-pdfs",
    ]
    for relative in on_demand:
        assert not (tmp_path / relative).exists(), relative

    manifest = (tmp_path / "_paper_source" / "manifest.json").read_text(encoding="utf-8")
    assert "core_sections" in manifest
    assert "on_demand_sections" in manifest
    assert "not precreated" in manifest


def test_wiki_setup_documents_lean_paper_source_bootstrap_contract():
    wiki_setup = (SKILLS / "wiki-setup" / "SKILL.md").read_text(encoding="utf-8")

    assert "core `_paper_source` bootstrap" in wiki_setup
    assert "raw/staging/meta/policies" in wiki_setup
    assert "on-demand" in wiki_setup
    assert "quarantine/evolution" in wiki_setup
    assert "raw/staging/runs/quarantine/evolution/meta roots" not in wiki_setup


def test_paper_wiki_documents_core_paper_source_bootstrap_without_requiring_on_demand_dirs():
    paper_wiki_root = ROOT.parent / "paper-wiki"
    files = [
        paper_wiki_root / "skills" / "paper-research-wiki" / "SKILL.md",
        paper_wiki_root / "docs" / "workflow.md",
        paper_wiki_root / "docs" / "paper-source-integration.md",
        paper_wiki_root / "skills" / "paper-research-wiki" / "workflows" / "check-wiki.md",
        paper_wiki_root / "skills" / "paper-research-wiki" / "workflows" / "extract-papers.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)

    for required in ["_paper_source/raw/", "_paper_source/staging/", "_paper_source/meta/", "_paper_source/policies/"]:
        assert required in combined
    assert "not a bootstrap failure" in combined
    assert "on-demand" in combined


def test_paper_source_stage1_aliases_are_natural_language_only():
    routing = (SKILLS / "routing.yaml").read_text(encoding="utf-8")
    discovery = (SKILLS / "paper-discovery" / "SKILL.md").read_text(encoding="utf-8")
    ingest = (SKILLS / "paper-ingest" / "SKILL.md").read_text(encoding="utf-8")

    for phrase in ["Paper Source", "PS", "用 PS 找论文", "用 PS 推进论文"]:
        assert phrase in "\n".join([routing, discovery, ingest])

    assert ("$" + "PS") not in routing
    assert ("$" + "PW") not in routing
    assert ("name: " + "ps") not in routing.lower()
    assert ("name: " + "pw") not in routing.lower()


def test_paper_source_support_directories_use_current_names():
    assert (SKILLS / "paper-source-paper-deposition" / "SKILL.md").is_file()
    assert not (SKILLS / "epi-paper-deposition").exists()
    assert (ROOT / "metric-packs" / "paper-source-quality-gates" / "manifest.json").is_file()
    assert not (ROOT / "metric-packs" / "epi-quality-gates").exists()


def test_paper_discovery_query_planner_wrapper_imports_current_runtime_package():
    wrapper = (SKILLS / "paper-discovery" / "scripts" / "query-planner.py").read_text(encoding="utf-8")

    assert "from paper_source.query_planner import main" in wrapper
    assert "from epi.query_planner import main" not in wrapper


def test_paper_source_runtime_does_not_ship_retired_epi_import_package():
    assert not (BUILD_ROOT / "epi").exists()


def test_paper_source_plugin_scripts_stay_below_line_limit():
    oversized = []
    for path in sorted((ROOT / "scripts").rglob("*.py")):
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > MAX_PLUGIN_SCRIPT_LINES:
            oversized.append(f"{path.relative_to(REPO_ROOT)}: {line_count}")

    assert oversized == []


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

        if skill_dir.name == "paper-discovery":
            metadata_text = "\n".join([short_description, default_prompt])
            assert "discover-papers" in metadata_text
            assert "natural-language paper search" in metadata_text


def test_skill_bundle_excludes_tracked_python_cache_artifacts_and_gitignore_covers_cache():
    result = subprocess.run(
        ["git", "ls-files", "plugins/paper-source/skills"],
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


def test_paper_discovery_output_format_uses_session_recommendations_contract():
    output_format = (SKILLS / "paper-discovery" / "references" / "output-format.md").read_text(encoding="utf-8")
    routing = (SKILLS / "routing.yaml").read_text(encoding="utf-8")
    discovery = (SKILLS / "paper-discovery" / "SKILL.md").read_text(encoding="utf-8")
    workflow = (SKILLS / "paper-discovery" / "workflows" / "run-discovery.md").read_text(encoding="utf-8")

    assert "report.json.session_recommendations" in output_format
    assert "discover-papers" in output_format
    assert "natural-language-default-discover-papers" in routing
    assert "For ordinary natural-language discovery, prefer `discover-papers`" in discovery
    assert "Use `dry-run` when" in discovery
    assert "Default natural-language discovery uses `discover-papers`" in workflow
    assert "session_recommendations.primary_recommendations" in output_format
    assert "session_recommendations.review_appendix" in output_format
    assert "session_recommendations.existing_library_appendix" in output_format
    assert "session_recommendations.no_primary_recommendations_summary" in output_format
    assert "report.json.discovery_context.discovery_progress" in output_format
    assert "progress-events.jsonl" in output_format
    assert "progress-summary.json" in output_format
    assert "session_recommendations.required_concept_group_rejects" in output_format
    assert "required_concept_group_mismatch:*" in output_format
    assert "dominant_blocking_reason" in output_format
    assert "top_blocked_candidates" in output_format
    assert "top blocked candidates are diagnostics only" in output_format
    assert "session_recommendations.doi_recovery_summary" in output_format
    assert "session_recommendations.doi_resolution_summary" in output_format
    assert "session_recommendations.doi_filtered_summary" in output_format
    assert "session_recommendations.verification_summary" in output_format
    assert "session_recommendations.overflow.hidden_count" in output_format
    assert "Run status and artifact path" in output_format
    assert "主推荐：无" in output_format
    assert "Render primary recommendations as a numbered list" in output_format
    assert "Journal or conference, year; DOI:" in output_format
    assert "summary：说明这篇论文用了什么方法，解决什么问题，效果、验证或证据如何" in output_format
    assert "The `summary：` line is required for each primary item" in output_format
    assert "method/system, target problem/task, and reported effect/result/validation evidence" in output_format
    assert "does not clearly state the effect or validation result" in output_format
    assert "quality_gate.dimensions.identity" in output_format
    assert "already-in-library" in output_format
    assert "DOI-missing papers into the primary list" in output_format
    assert "never call those items recommendations" in output_format
    assert "新增待复核候选" in output_format
    assert "库中已有，可回看" in output_format
    assert "short explanatory sentence plus a Markdown table" in output_format
    assert "`论文`, `年份`, `状态`, and `入口`" in output_format
    assert "这些论文已在当前 wiki/raw library 中命中，未重复放入新推荐" in output_format
    assert "one-line semicolon-separated list" in output_format
    assert "missing_required_doi" in output_format
    assert "DOI待补" in output_format
    assert "doi_url" in output_format
    assert "primary_url" in output_format
    assert "citation_count_source" in output_format
    assert "missing provider citation field is not the same as a verified `0`" in output_format
    assert "Paper Source scripts do not generate semantic Chinese summaries" in output_format
    assert "do not list every kept paper in `推荐优先看`" in output_format

    search_protocol = (SKILLS / "paper-discovery" / "references" / "search-protocol.md").read_text(encoding="utf-8")
    assert "must not be recommended again" in search_protocol
    assert "not provide a strong semantic reranker" in search_protocol
    assert "cross-discipline quality gate" in search_protocol
    assert "saturated positive keyword matches" in search_protocol
    assert "priority topic-fit weight" in search_protocol
    assert "10.48550/arXiv.<base_id>" in search_protocol
    assert "targeted DOI recovery" in search_protocol
    assert "provider_records.grok_search.status=ok" in search_protocol
    assert "canonical lightweight backlog" in search_protocol
    assert "do not rescan formal pages or raw metadata" in search_protocol
    assert "missing/unreadable reference-index fallback" in search_protocol

    quality_gate = (SKILLS / "paper-discovery" / "references" / "quality-gate.md").read_text(encoding="utf-8")
    assert "The gate is cross-discipline" in quality_gate
    assert "`priority_keywords`" in quality_gate
    assert "`positive_keywords_saturated`" in quality_gate
    assert "`keyword_coverage_score`" in quality_gate
    assert "`quality_gate.dimensions`" in quality_gate

    ranking_rubric = (SKILLS / "paper-discovery" / "references" / "ranking-rubric.md").read_text(encoding="utf-8")
    assert "`topic_fit_basis`" in ranking_rubric
    assert "`keyword_topic_score`" in ranking_rubric
    assert "`keyword_coverage_score`" in ranking_rubric
    assert "`quality_gate.dimensions`" in ranking_rubric


def test_paper_source_paper_deposition_is_thin_handoff_cleanup_entry():
    deposition = (SKILLS / "paper-source-paper-deposition" / "SKILL.md").read_text(encoding="utf-8")
    formal_workflow = (
        SKILLS / "paper-source-paper-deposition" / "workflows" / "formal-wiki-write.md"
    ).read_text(encoding="utf-8")
    combined = "\n".join([deposition, formal_workflow])

    assert "workflows/formal-wiki-write.md" in deposition
    assert "wiki-ingest-brief.json" in combined
    assert "Historical `wiki_deposition_task.json` cleanup" in combined
    assert "epi-wiki-deposition" not in combined
    assert "legacy `_epi/`" not in combined
    assert "legacy `_paper_source/`" not in combined
    assert "Existing `_paper_source/` handoffs remain readable as legacy artifacts." not in combined
    assert "$paper-research-wiki" in combined
    assert "cleanup workflow" in combined
    assert "llm-wiki" not in combined
    assert "wiki-stage-commit" not in combined
    assert "Required frontmatter fields" not in combined
    assert "must not enter the formal graph" in combined


def test_paper_source_wiki_boundary_skill_docs_are_brief_first():
    files = [
        SKILLS / "paper-ingest" / "SKILL.md",
        SKILLS / "paper-ingest" / "workflows" / "approval-and-trigger.md",
        SKILLS / "wiki-setup" / "SKILL.md",
        SKILLS / "wiki-provenance" / "SKILL.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)

    for phrase in [
        "wiki-ingest-brief.json",
        "canonical Paper Source-to-Paper Wiki handoff",
        "wiki_deposition_task.json",
        "historical",
        "paper-research-wiki",
        "paper-source-paper-deposition",
        "external wiki skills are optional helpers",
        "record-wiki-ingest",
        "final-source-review.json",
    ]:
        assert phrase in combined


def test_current_skill_docs_prefer_current_env_names_without_old_alias_fallbacks():
    mineru = (SKILLS / "mineru-paper-parser" / "SKILL.md").read_text(encoding="utf-8")
    prepare_ranked = (
        SKILLS / "paper-ingest" / "workflows" / "prepare-ranked.md"
    ).read_text(encoding="utf-8")
    combined = "\n".join([mineru, prepare_ranked])

    assert "PAPER_SOURCE_MINERU_TIMEOUT" in combined
    assert "EPI_MINERU_TIMEOUT" not in combined
    assert "set `EPI_MINERU_TIMEOUT`" not in combined
    assert "reads `EPI_MINERU_TIMEOUT`" not in combined


def test_wiki_setup_marks_retired_root_as_migration_input_only():
    wiki_setup = (SKILLS / "wiki-setup" / "SKILL.md").read_text(encoding="utf-8")

    assert "Historical `_epi` roots are migration inputs only" in wiki_setup
    assert "Existing `_epi` roots remain legacy-readable" not in wiki_setup
    assert "Existing `_paper_source` roots remain legacy-readable" not in wiki_setup
    assert "legacy `_epi\\meta\\paper-source-config.yaml`" not in wiki_setup
    assert "legacy `_paper_source\\meta\\paper-source-config.yaml`" not in wiki_setup


def test_wiki_setup_uses_code_span_for_obsidian_pdf_uri_example():
    text = (SKILLS / "wiki-setup" / "SKILL.md").read_text(encoding="utf-8")

    assert "`obsidian://open?vault=<vault>&file=_paper_source%2Fraw%2F<slug>%2Fpaper.pdf`" in text
    assert "](obsidian://open?vault=<vault>&file=_paper_source%2Fraw%2F<slug>%2Fpaper.pdf)" not in text


def test_page_provenance_migrates_legacy_internal_pdf_links_to_title_display_pdf_sources():
    page_provenance = (
        SKILLS / "wiki-provenance" / "references" / "page-provenance.md"
    ).read_text(encoding="utf-8")

    assert "_paper_source/raw/<slug>/paper.pdf" in page_provenance
    assert "Frontmatter `sources` must contain title-display Markdown links to canonical source PDFs" in page_provenance
    assert "link text must be the source paper title" in page_provenance
    assert "Retired `_epi` links and internal PDF wikilinks are repair candidates" in page_provenance
    assert "normal evidence fallbacks" in page_provenance
    assert "Legacy `_epi` or `_paper_source` wikilinks may be read for compatibility" not in page_provenance
    assert (
        "recorded formal pages must convert them to canonical `_paper_source` title-display PDF links"
        in page_provenance
    )
    assert "[[_epi/raw/<slug>/paper.pdf|<slug>]]" not in page_provenance
    assert "legacy `\"[[_paper_source/raw/<slug>/paper.pdf|<slug>]]\"`" not in page_provenance


def test_paper_wiki_qmd_boundary_is_explicit_in_plugin_contracts():
    files = [
        ROOT / "docs" / "workflow.md",
        ROOT / "docs" / "paper-source-linkage.md",
        ROOT / "docs" / "structure.md",
        SKILLS / "paper-source-paper-deposition" / "SKILL.md",
        SKILLS / "paper-source-paper-deposition" / "workflows" / "formal-wiki-write.md",
        ROOT / "scripts" / "build" / "paper_source" / "wiki_contracts.py",
        ROOT / "scripts" / "build" / "paper_source" / "wiki_init.py",
        ROOT / "scripts" / "build" / "paper_source" / "stage_wiki.py",
        ROOT / "scripts" / "build" / "paper_source" / "wiki_ingest_handoff.py",
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
        "_paper_source/**",
        "_paper_source/meta/formal-page-snapshots/",
        "MinerU source Markdown",
        ".obsidian/**",
        ".claude/**",
    ]:
        assert ignored in combined


def test_paper_source_formal_deposition_route_is_handoff_cleanup():
    routing = _load_routing()
    routes = routing["routes"]

    assert routes["wiki_setup"]["category"] == "primary"

    deposition = routes["paper_source_paper_deposition"]
    assert deposition["category"] == "maintenance"
    assert deposition["skill"] == "paper-source-paper-deposition/SKILL.md"
    assert "$paper-research-wiki" in "\n".join(deposition.get("notes", []))
    assert "epi-wiki-deposition" not in "\n".join(map(str, deposition.get("triggers", [])))


def test_discover_to_handoff_has_single_route_owner():
    routing = _load_routing()
    routes = routing["routes"]

    owners = [
        name
        for name, route in routes.items()
        if "discover-to-handoff" in route.get("triggers", [])
    ]
    assert owners == ["paper_ingest"], owners
