import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "paper-wiki"
PAPER_SOURCE_PLUGIN = ROOT / "plugins" / "paper-source"
PUBLIC_SKILL = PLUGIN / "skills" / "paper-research-wiki"
MARKETPLACES = [
    ROOT / "marketplace.json",
    ROOT / ".agents" / "plugins" / "marketplace.json",
]
WORKFLOWS = {
    "ask-wiki.md",
    "extract-papers.md",
    "check-wiki.md",
    "zotero-status.md",
    "zotero-apply.md",
    "update-wiki.md",
    "redo-extraction.md",
    "maintain-figures.md",
}
PUBLIC_SKILLS = {"paper-research-wiki"}
SUPPORT_SKILLS = {"paper-wiki-language"}
REFERENCES = {
    "paper-source-artifact-contract.md",
    "page-provenance.md",
    "page-family-contract.md",
    "references-page-anatomy.md",
    "survey-page-anatomy.md",
    "upstream-obsidian-wiki-map.md",
}
FORMAL_PAGE_FAMILIES = {
    "references/",
    "concepts/",
    "derivations/",
    "experiments/",
    "synthesis/",
    "reports/",
    "opportunities/",
}
FORBIDDEN_FORMAL_ROOTS = {
    "_paper_source/",
    "_raw/",
    "_staging/",
    "_runs/",
    "_quarantine/",
    ".obsidian/",
}


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_openai_metadata(metadata_path: Path):
    text = _read(metadata_path)
    try:
        import yaml
    except ModuleNotFoundError:
        yaml = None
    if yaml is not None:
        return yaml.safe_load(text)

    interface = {}
    for line in text.splitlines():
        match = re.match(r'^\s{2}([a-z_]+):\s+"([^"]*)"$', line)
        if match:
            key, value = match.groups()
            interface[key] = value
    return {"interface": interface}


def _skill_body_line_count(path: Path) -> int:
    lines = _read(path).splitlines()
    if lines and lines[0] == "---":
        for index, line in enumerate(lines[1:], start=1):
            if line == "---":
                return len(lines[index + 1 :])
    return len(lines)


def _load_paper_wiki_routing():
    text = _read(PLUGIN / "skills" / "routing.yaml")
    try:
        import yaml
    except ModuleNotFoundError:
        yaml = None
    if yaml is not None:
        return yaml.safe_load(text)

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
            elif key in {"triggers", "workflows", "references", "rules"}:
                current[key] = []
            continue
        list_match = re.match(r"^      -\s+(.*)$", line)
        if list_match and current is not None and current_key:
            current.setdefault(current_key, []).append(list_match.group(1))
    return data


def _required_fields_from_canonical_standard(text: str) -> list[str]:
    match = re.search(
        r"Required frontmatter fields:\n\n(?P<body>(?:- `[^`]+:`[^\n]*\n)+)",
        text,
    )
    assert match
    fields = []
    for line in match.group("body").splitlines():
        field_match = re.match(r"- `([^`:]+):`(?P<tail>.*)$", line)
        assert field_match
        field, tail = field_match.groups()
        if " when " not in tail:
            fields.append(field)
    return fields


def _required_fields_from_focused_frontmatter_rule(text: str) -> list[str]:
    match = re.search(r"Required frontmatter fields: (?P<fields>[^.]+)\.", text)
    assert match
    return re.findall(r"`([^`]+)`", match.group("fields"))


def test_plugin_manifest_exposes_simple_user_prompts():
    manifest = _read_json(PLUGIN / ".codex-plugin" / "plugin.json")

    assert manifest["name"] == "paper-wiki"
    assert manifest["version"] == "1.3.1"
    assert manifest["skills"] == "./skills/"
    assert manifest["interface"]["displayName"] == "Paper Wiki"
    assert "Paper Wiki" in manifest["description"]
    assert "academic paper knowledge" in manifest["description"]
    assert "source-map-grounded" in manifest["description"]
    assert "formula reasoning chains" in manifest["interface"]["longDescription"]
    assert "evidence figure cards" in manifest["interface"]["longDescription"]
    assert "graph visibility" in manifest["interface"]["longDescription"]
    assert "link repair" in manifest["interface"]["longDescription"]
    assert "QMD-compatible" in manifest["interface"]["longDescription"]
    assert "post-task check" in manifest["interface"]["longDescription"]
    assert "_meta/reference-index.json" in manifest["interface"]["longDescription"]
    assert "paper-wiki-zotero-sync-report-v1" in manifest["interface"]["longDescription"]
    assert "wiki-scoped BibTeX" in manifest["interface"]["longDescription"]
    assert "read-only Zotero status/dry-run" in manifest["interface"]["longDescription"]
    assert "one-run plan-hash approval" in manifest["interface"]["longDescription"]
    assert "selected-target checks" in manifest["interface"]["longDescription"]
    assert "references.bib refresh" in manifest["interface"]["longDescription"]
    assert "summary-plus-top-20 Zotero-only" in manifest["interface"]["longDescription"]
    assert manifest["interface"]["shortDescription"].startswith("v1.3.1 | Paper Wiki:")
    for phrase in ["Paper Wiki", "ask", "deposit", "check", "Zotero status/dry-run/apply", "update", "relink", "redo"]:
        assert phrase in manifest["interface"]["shortDescription"]
    prompt_text = "\n".join(manifest["interface"]["defaultPrompt"])
    for phrase in ["Paper Wiki", "PW", "Paper Source", "提取", "提问", "检测", "关系图谱", "Zotero", "dry-run", "apply", "更新", "沉淀", "link", "QMD"]:
        assert phrase in prompt_text


def test_paper_source_manifest_describes_brief_first_paper_wiki_boundary():
    manifest = _read_json(PAPER_SOURCE_PLUGIN / ".codex-plugin" / "plugin.json")

    assert manifest["version"] == "2.9.1"
    assert manifest["name"] == "paper-source"
    assert manifest["interface"]["displayName"] == "Paper Source"
    assert "Paper Source" in manifest["description"]
    assert "Paper Wiki-compatible" in manifest["description"]
    assert manifest["interface"]["shortDescription"].startswith("v2.9.1 | Paper Source:")
    assert "health doctor" in manifest["interface"]["shortDescription"]
    assert "MCP/runtime diagnostics" in manifest["interface"]["shortDescription"]
    assert "graph visibility" in manifest["interface"]["shortDescription"]
    assert "config diagnostics" in manifest["interface"]["shortDescription"]
    assert "CJK query planning" in manifest["interface"]["shortDescription"]
    assert "progress telemetry" in manifest["interface"]["shortDescription"]
    assert "recommend" in manifest["interface"]["shortDescription"]
    assert "benchmark gates" in manifest["interface"]["shortDescription"]
    assert "Grok diagnostics" in manifest["interface"]["shortDescription"]
    assert "required concept groups" in manifest["interface"]["shortDescription"]
    assert "recall/risk checks" in manifest["interface"]["shortDescription"]
    assert "record" in manifest["interface"]["shortDescription"]
    assert "Paper Source" in manifest["interface"]["longDescription"]
    assert "Paper Wiki" in manifest["interface"]["longDescription"]
    assert "empty graph.json search plus app.json userIgnoreFilters" in manifest["interface"]["longDescription"]
    assert "session_recommendations" in manifest["interface"]["longDescription"]
    assert "zotero-dedupe-record.json" in manifest["interface"]["longDescription"]
    assert "already_in_zotero_not_wiki" in manifest["interface"]["longDescription"]
    assert "possible_zotero_duplicate" in manifest["interface"]["longDescription"]
    assert "progress-events.jsonl" in manifest["interface"]["longDescription"]
    assert "report.json.discovery_context.discovery_progress" in manifest["interface"]["longDescription"]
    assert "required concept groups" in manifest["interface"]["longDescription"]
    assert "CJK topic terms" in manifest["interface"]["longDescription"]
    assert "shared timeout budgets" in manifest["interface"]["longDescription"]
    assert "discovery-benchmark gates" in manifest["interface"]["longDescription"]
    assert "provider-supplied official versions or related papers" in manifest["interface"]["longDescription"]
    assert "high-quality supplemental recall" in manifest["interface"]["longDescription"]
    assert "retry outcomes" in manifest["interface"]["longDescription"]
    assert "provider quality-risk checks" in manifest["interface"]["longDescription"]
    assert "normalized citation ranking" in manifest["interface"]["longDescription"]
    assert "config/agent-plan quality-evidence lexicons" in manifest["interface"]["longDescription"]
    assert "retrieval and metadata coverage rather than a semantic quality ranker" in manifest["interface"]["longDescription"]
    assert "non-Reject session_recommendations" in manifest["interface"]["longDescription"]
    assert "discover-papers" in manifest["interface"]["longDescription"]
    assert "grok-search-rs MCP" in manifest["interface"]["longDescription"]
    assert "plugin-installed grok-search-rs MCP self-registration" in manifest["interface"]["longDescription"]
    assert "Codex automation approval" in manifest["interface"]["longDescription"]


def test_marketplaces_register_paper_research_wiki():
    for marketplace_path in MARKETPLACES:
        marketplace = _read_json(marketplace_path)
        entries = {entry["name"]: entry for entry in marketplace["plugins"]}

        assert "paper-wiki" in entries, marketplace_path
        assert "paper-source" in entries, marketplace_path
        entry = entries["paper-wiki"]
        assert entry["source"] == {
            "source": "local",
            "path": "./plugins/paper-wiki",
        }
        assert entry["policy"] == {
            "installation": "AVAILABLE",
            "authentication": "ON_INSTALL",
        }
        assert entry["category"] == "Productivity"


def test_plugin_has_one_public_skill_plus_language_gate():
    skill_dirs = {
        path.name
        for path in (PLUGIN / "skills").iterdir()
        if path.is_dir() and (path / "SKILL.md").exists()
    }
    assert skill_dirs == PUBLIC_SKILLS | SUPPORT_SKILLS
    language_skill = _read(PLUGIN / "skills" / "paper-wiki-language" / "SKILL.md")
    assert "source-grounded Chinese research-wiki prose" in language_skill
    assert "Language Gate" in language_skill
    assert "references/style-guide.md" in language_skill


def test_paper_wiki_ui_metadata_keeps_formal_wiki_boundary():
    metadata = _load_openai_metadata(PUBLIC_SKILL / "agents" / "openai.yaml")
    interface = metadata["interface"]
    combined = "\n".join(
        [
            interface.get("short_description", ""),
            interface.get("default_prompt", ""),
            _read(PLUGIN / ".codex-plugin" / "plugin.json"),
        ]
    )

    for phrase in ["提取", "沉淀", "提问", "检测", "更新", "重link", "重做"]:
        assert phrase in combined

    for forbidden in ["discover-papers", "source-staging", "record-human-approval"]:
        assert forbidden not in combined


def test_paper_wiki_all_skill_entrypoints_stay_thin():
    for skill_name in PUBLIC_SKILLS | SUPPORT_SKILLS:
        skill_path = PLUGIN / "skills" / skill_name / "SKILL.md"
        assert _skill_body_line_count(skill_path) <= 90, skill_name


def test_paper_wiki_support_skill_entrypoints_stay_thin_and_route_to_style_guide():
    language_skill_path = PLUGIN / "skills" / "paper-wiki-language" / "SKILL.md"
    style_guide_path = PLUGIN / "skills" / "paper-wiki-language" / "references" / "style-guide.md"

    assert _skill_body_line_count(language_skill_path) <= 90
    assert style_guide_path.exists()

    language_skill = _read(language_skill_path)
    style_guide = _read(style_guide_path)

    assert "references/style-guide.md" in language_skill
    for phrase in [
        "Voice Target",
        "Chinese Style Rules",
        "Page-Family Voice",
        "Claim-Preserving Rewrite Pattern",
    ]:
        assert phrase in style_guide


def test_public_skill_routes_natural_paper_source_deposition_actions():
    skill = _read(PUBLIC_SKILL / "SKILL.md")

    for phrase in [
        "提取",
        "检测",
        "更新",
        "沉淀",
        "提问",
        "问 wiki",
        "问论文 wiki",
        "根据 wiki 回答",
        "查询论文 wiki",
        "直接沉淀",
        "继续上次",
        "默认",
        "重link",
        "重做",
        "重新提取",
        "更详细",
        "批量",
        "relink",
        "redo",
        "extract",
        "check",
        "ask wiki",
        "ask paper wiki",
        "what does the wiki say",
        "update",
        "公式推理链",
        "图片证据",
        "图文证据卡",
        "source map",
        "source-map-first",
    ]:
        assert phrase in skill
    assert (
        "| 重做 / 重新提取 / 更详细提取 / 批量重提取 / 公式推理链 / 图片证据 / 图文证据卡 / "
        "source map / source-map-first / redo / deep extraction | `workflows/redo-extraction.md` |"
    ) in skill
    assert (
        "| 提问 / 问 wiki / 问论文 wiki / 根据 wiki 回答 / 查询论文 wiki / "
        "ask wiki / ask paper wiki / what does the wiki say | `workflows/ask-wiki.md` |"
    ) in skill
    for workflow in WORKFLOWS:
        assert f"workflows/{workflow}" in skill
        path = PUBLIC_SKILL / "workflows" / workflow
        assert path.exists(), workflow
        assert path.read_text(encoding="utf-8").strip(), workflow


def test_paper_wiki_skill_routing_manifest_matches_public_workflows():
    routing_path = PLUGIN / "skills" / "routing.yaml"
    assert routing_path.exists()

    routing = _load_paper_wiki_routing()
    assert routing["schema_version"] == "paper-wiki-skill-routing-v1"
    assert routing["source_of_truth"] == "skills/routing.yaml"
    assert len(routing["always_read"]) <= 3
    assert "paper-research-wiki/references/upstream-obsidian-wiki-map.md" not in routing["always_read"]
    assert "../rules/wiki-writing-standard-brief.md" in routing["always_read"]
    assert "../rules/wiki-writing-standard.md" not in routing["always_read"]

    routes = routing["routes"]
    assert set(routes) == {
        "extract_papers",
        "check_wiki",
        "zotero_status",
        "zotero_apply",
        "ask_wiki",
        "redo_extraction",
        "update_wiki",
        "maintain_figures",
        "language_gate",
    }

    routed_workflows = {
        Path(workflow).name
        for route in routes.values()
        for workflow in route.get("workflows", [])
    }
    assert routed_workflows == WORKFLOWS

    for route_name, route in routes.items():
        assert route.get("skill") in {
            "paper-research-wiki/SKILL.md",
            "paper-wiki-language/SKILL.md",
        }, route_name
        assert route.get("triggers"), route_name
        assert any(re.search(r"[\u4e00-\u9fff]", str(trigger)) for trigger in route["triggers"]), route_name

    redo_triggers = set(routes["redo_extraction"]["triggers"])
    for phrase in [
        "公式推理",
        "公式推理链",
        "图片证据",
        "图文结合",
        "图文证据卡",
        "source map",
        "source-map-first",
        "source-map-grounded extraction",
        "formula reasoning chains",
        "evidence figure cards",
    ]:
        assert phrase in redo_triggers

    check_triggers = set(routes["check_wiki"]["triggers"])
    for phrase in ["检查关系图谱", "图谱健康检查", "graph health check"]:
        assert phrase in check_triggers

    zotero_triggers = set(routes["zotero_status"]["triggers"])
    for phrase in ["Paper Wiki Zotero status", "Paper Wiki Zotero dry-run", "Zotero-only 文献", "zotero sync status"]:
        assert phrase in zotero_triggers
    assert routes["zotero_status"]["workflows"] == ["paper-research-wiki/workflows/zotero-status.md"]
    assert any("read-only by default" in note for note in routes["zotero_status"].get("notes", []))

    apply_triggers = set(routes["zotero_apply"]["triggers"])
    for phrase in ["Paper Wiki Zotero apply", "Zotero 同步应用", "link Zotero items", "refresh references.bib"]:
        assert phrase in apply_triggers
    assert routes["zotero_apply"]["workflows"] == ["paper-research-wiki/workflows/zotero-apply.md"]
    assert any("one-run approval" in note for note in routes["zotero_apply"].get("notes", []))
    apply_workflow = _read(PUBLIC_SKILL / "workflows" / "zotero-apply.md")
    for phrase in ["one-run approval", "plan hash", "selected target", "references.bib", "sync report"]:
        assert phrase in apply_workflow

    update_triggers = set(routes["update_wiki"]["triggers"])
    for phrase in ["关系图谱出错", "图谱只剩 index", "修复关系图谱", "graph only index", "repair Obsidian graph visibility"]:
        assert phrase in update_triggers

    skill = _read(PUBLIC_SKILL / "SKILL.md")
    assert "../routing.yaml" in skill
    assert "routing manifest" in skill

    assert "paper-wiki-language/references/style-guide.md" in routes["language_gate"].get("references", [])

    maintain = routes["maintain_figures"]
    assert maintain["workflows"] == ["paper-research-wiki/workflows/maintain-figures.md"]
    assert "图谱命名" in maintain["triggers"]
    assert "repair image paths" in maintain["triggers"]
    assert any("do not rename raw MinerU image assets" in note for note in maintain.get("notes", []))


def test_paper_wiki_routes_read_only_wiki_questions_to_ask_workflow():
    routing = _load_paper_wiki_routing()
    ask_route = routing["routes"]["ask_wiki"]
    skill = _read(PUBLIC_SKILL / "SKILL.md")
    workflow = _read(PUBLIC_SKILL / "workflows" / "ask-wiki.md")

    assert ask_route["category"] == "primary"
    assert ask_route["skill"] == "paper-research-wiki/SKILL.md"
    assert ask_route["workflows"] == ["paper-research-wiki/workflows/ask-wiki.md"]
    for phrase in [
        "提问",
        "问 wiki",
        "问论文 wiki",
        "根据 wiki 回答",
        "查询论文 wiki",
        "ask wiki",
        "ask paper wiki",
        "what does the wiki say",
        "research question",
    ]:
        assert phrase in ask_route["triggers"]
        assert phrase in skill or phrase in workflow


def test_ask_wiki_workflow_is_read_only_graph_first_and_correction_candidate_based():
    workflow = _read(PUBLIC_SKILL / "workflows" / "ask-wiki.md")
    routing = _read(PLUGIN / "skills" / "routing.yaml")
    workflow_doc = _read(PLUGIN / "docs" / "workflow.md")
    structure_doc = _read(PLUGIN / "docs" / "structure.md")
    integration_doc = _read(PLUGIN / "docs" / "paper-source-integration.md")
    combined = "\n".join([workflow, routing, workflow_doc, structure_doc, integration_doc])

    for phrase in [
        "read-only",
        "no `log.md`",
        "do not write `log.md`",
        "do not write formal pages",
        "do not refresh QMD",
        "do not write Paper Source artifacts",
        "formal Obsidian graph",
        "backlinks",
        "outlinks",
        "co-links",
        "QMD is an optional accelerator",
        "fallback",
        "【Wiki 证据】",
        "【综合判断】",
        "【推断】",
        "【边界/不确定】",
        "correction candidates",
        "ask before repair",
    ]:
        assert phrase in combined

    assert "Question -> Scope -> Formal graph retrieval -> Evidence check -> Answer labels -> Correction candidates -> Stop" in workflow_doc
    assert "read-only `ask_wiki`" in integration_doc
    assert "paper-wiki-record-request.json" in integration_doc
    assert "ask-wiki does not write `paper-wiki-record-request.json`" in integration_doc


def test_public_skill_references_internal_contract_files():
    skill = _read(PUBLIC_SKILL / "SKILL.md")

    for reference in REFERENCES:
        assert f"references/{reference}" in skill
        path = PUBLIC_SKILL / "references" / reference
        assert path.exists(), reference
        assert path.read_text(encoding="utf-8").strip(), reference


def test_public_skill_defaults_paper_source_wiki_requests_to_deposition():
    skill = _read(PUBLIC_SKILL / "SKILL.md")

    for phrase in [
        "Paper Source",
        "ready",
        "preflight",
        "沉淀",
        "wiki-ingest-brief.json",
        "workflows/extract-papers.md",
        "workflows/check-wiki.md",
    ]:
        assert phrase in skill
    assert "only Paper Source-to-Paper Wiki handoff contract" in skill


def test_required_docs_and_rules_exist():
    required = [
        "AGENTS.md",
        "docs/workflow.md",
        "docs/structure.md",
        "docs/paper-source-integration.md",
        "docs/provenance.md",
        "docs/privacy.md",
        "docs/terms.md",
        "rules/source-trust.md",
        "rules/page-families.md",
        "rules/formal-page-frontmatter.md",
        "rules/wiki-writing-standard.md",
    ]

    for relative in required:
        path = PLUGIN / relative
        assert path.exists(), relative
        assert path.read_text(encoding="utf-8").strip(), relative


def test_page_family_rules_capture_formal_and_forbidden_roots():
    text = _read(PLUGIN / "rules" / "page-families.md")

    for family in FORMAL_PAGE_FAMILIES:
        assert family in text
    for root in FORBIDDEN_FORMAL_ROOTS:
        assert root in text


def test_paper_source_integration_docs_name_handoff_and_record_contracts():
    text = _read(PLUGIN / "docs" / "paper-source-integration.md")

    for phrase in [
        "canonical Paper Source-to-Paper Wiki handoff",
        "wiki-ingest-brief.json",
        "final-source-review.json",
        "record-wiki-ingest",
        "paper-gate",
        "human approval",
    ]:
        assert phrase in text
    assert "Historical aliases are not Paper Wiki user entrypoints" in text


def test_provenance_docs_preserve_claim_support_statuses():
    text = _read(PLUGIN / "docs" / "provenance.md")

    for phrase in [
        "source-grounded",
        "metadata-only",
        "inferred",
        "unsupported",
        "evidence address",
        "formula",
        "figure",
    ]:
        assert phrase in text


def test_upstream_obsidian_wiki_map_covers_core_skill_families():
    text = _read(PUBLIC_SKILL / "references" / "upstream-obsidian-wiki-map.md")

    for phrase in [
        "Ar9av/obsidian-wiki",
        "wiki-ingest",
        "wiki-update",
        "wiki-status",
        "cross-linker",
        "tag-taxonomy",
        "wiki-lint",
    ]:
        assert phrase in text


def test_upstream_obsidian_wiki_map_is_internalized_not_runtime_fetch():
    text = _read(PUBLIC_SKILL / "references" / "upstream-obsidian-wiki-map.md")

    for phrase in [
        "design source, not a runtime source of truth",
        "do not fetch or search Ar9av/obsidian-wiki",
        "normal Paper Wiki runs",
        "local Paper Wiki workflows",
        "upstream repository only when maintaining Paper Wiki",
    ]:
        assert phrase in text


def test_paper_wiki_internalizes_link_repair_qmd_and_post_task_checks():
    skill = _read(PUBLIC_SKILL / "SKILL.md")
    standard = _read(PLUGIN / "rules" / "wiki-writing-standard.md")
    upstream = _read(PUBLIC_SKILL / "references" / "upstream-obsidian-wiki-map.md")
    check = _read(PUBLIC_SKILL / "workflows" / "check-wiki.md")
    update = _read(PUBLIC_SKILL / "workflows" / "update-wiki.md")
    extract = _read(PUBLIC_SKILL / "workflows" / "extract-papers.md")
    redo = _read(PUBLIC_SKILL / "workflows" / "redo-extraction.md")
    workflow_doc = _read(PLUGIN / "docs" / "workflow.md")

    for text in [skill, standard, upstream, check, update, extract, redo, workflow_doc]:
        assert "post-task check" in text

    for text in [check, update, upstream, workflow_doc]:
        for phrase in [
            "broken wikilinks",
            "ambiguous aliases",
            "duplicate concept owners",
            "forbidden internal links",
            "relationship direction",
        ]:
            assert phrase in text

    for text in [check, update, extract, redo, upstream, workflow_doc]:
        for phrase in [
            "QMD",
            "qmd update",
            "qmd embed",
            "fallback to manifest",
            "block on qmd query",
        ]:
            assert phrase.lower() in text.lower()

    for text in [extract, redo, update]:
        assert "Run `workflows/check-wiki.md` after writing" in text


def test_paper_wiki_declares_closed_loop_boundary_and_completion_definition():
    skill = _read(PUBLIC_SKILL / "SKILL.md")
    standard = _read(PLUGIN / "rules" / "wiki-writing-standard.md")
    workflow_doc = _read(PLUGIN / "docs" / "workflow.md")
    paper_source_integration = _read(PLUGIN / "docs" / "paper-source-integration.md")

    for text in [skill, workflow_doc]:
        assert "Check -> Diagnose -> Plan -> Act -> Verify -> Refresh -> Record -> Next" in text

    for text in [skill, standard, workflow_doc]:
        assert (
            "A Paper Wiki task is not complete until formal pages, tracking files, graph links, "
            "taxonomy, provenance, language gate, QMD freshness, and Paper Source record readiness "
            "have been checked or explicitly reported as skipped with reason."
        ) in text

    for text in [skill, workflow_doc, paper_source_integration]:
        for phrase in [
            "Paper Wiki owns",
            "Paper Source owns",
            "paper discovery",
            "MinerU parsing",
            "paper-gate",
            "human approval",
            "record-wiki-ingest",
            "final-source-review.json",
            "_meta/reference-index.json",
        ]:
            assert phrase in text


def test_paper_wiki_refreshes_reference_index_after_reference_page_writes():
    skill = _read(PUBLIC_SKILL / "SKILL.md")
    standard = _read(PLUGIN / "rules" / "wiki-writing-standard.md")
    brief = _read(PLUGIN / "rules" / "wiki-writing-standard-brief.md")
    workflow_doc = _read(PLUGIN / "docs" / "workflow.md")
    integration = _read(PLUGIN / "docs" / "paper-source-integration.md")
    structure = _read(PLUGIN / "docs" / "structure.md")
    check = _read(PUBLIC_SKILL / "workflows" / "check-wiki.md")
    extract = _read(PUBLIC_SKILL / "workflows" / "extract-papers.md")
    update = _read(PUBLIC_SKILL / "workflows" / "update-wiki.md")
    redo = _read(PUBLIC_SKILL / "workflows" / "redo-extraction.md")
    combined = "\n".join([skill, standard, brief, workflow_doc, integration, structure, check, extract, update, redo])

    for phrase in [
        "scripts/refresh_reference_index.py",
        "_meta/reference-index.json",
        "paper-research-reference-index-v1",
        "canonical lightweight backlog",
        "changed reference page/source id appears in the index",
    ]:
        assert phrase in combined


def test_paper_wiki_does_not_claim_to_refresh_paper_source_record_files():
    standard = _read(PLUGIN / "rules" / "wiki-writing-standard.md")
    update = _read(PUBLIC_SKILL / "workflows" / "update-wiki.md")
    redo = _read(PUBLIC_SKILL / "workflows" / "redo-extraction.md")
    extract = _read(PUBLIC_SKILL / "workflows" / "extract-papers.md")
    check = _read(PUBLIC_SKILL / "workflows" / "check-wiki.md")
    integration = _read(PLUGIN / "docs" / "paper-source-integration.md")

    combined = "\n".join([standard, update, redo, extract, check, integration])

    assert "Paper Source owns human approval records and `record-wiki-ingest`" in combined
    assert "previous `wiki-ingest-record.json`" in combined
    assert "staging/raw `wiki-ingest-record.json`" not in combined
    assert "Refresh manifest or `.manifest.json`, `final-source-review.json`, staging/raw `wiki-ingest-record.json`" not in combined
    assert "Paper Wiki records readiness; Paper Source writes or replaces `wiki-ingest-record.json`" in combined


def test_paper_wiki_documents_ask_mode_paper_source_record_request_handoff():
    standard = _read(PLUGIN / "rules" / "wiki-writing-standard.md")
    extract = _read(PUBLIC_SKILL / "workflows" / "extract-papers.md")
    update = _read(PUBLIC_SKILL / "workflows" / "update-wiki.md")
    redo = _read(PUBLIC_SKILL / "workflows" / "redo-extraction.md")
    maintain = _read(PUBLIC_SKILL / "workflows" / "maintain-figures.md")
    integration = _read(PLUGIN / "docs" / "paper-source-integration.md")
    combined = "\n".join([standard, extract, update, redo, maintain, integration])

    for phrase in [
        "paper-wiki-record-request.json",
        "schema_version: paper-wiki-record-request-v1",
        "automation_mode: ask",
        "record-wiki-ingest --from-paper-wiki-request",
        "Paper Wiki writes the request artifact; Paper Source consumes it",
    ]:
        assert phrase in combined

    assert "Paper Wiki writes or replaces `wiki-ingest-record.json`" not in combined


def test_paper_wiki_documents_codex_automation_handoff_without_owning_paper_source_state():
    skill = _read(PUBLIC_SKILL / "SKILL.md")
    workflow = _read(PUBLIC_SKILL / "workflows" / "extract-papers.md")
    artifact_contract = _read(PUBLIC_SKILL / "references" / "paper-source-artifact-contract.md")
    integration = _read(PLUGIN / "docs" / "paper-source-integration.md")
    workflow_doc = _read(PLUGIN / "docs" / "workflow.md")
    combined = "\n".join([skill, workflow, artifact_contract, integration, workflow_doc])

    for phrase in [
        "wiki-agent-trigger.json",
        "automation_handoff",
        "codex-automation:<task-id>",
        "explicit Codex automation",
        "ordinary approval-waiting handoff",
        "automation-approved ready",
        "paper-wiki-record-request-v1",
        "automation_mode: ask",
    ]:
        assert phrase in combined

    for phrase in [
        "does not write `human-approval.json`",
        "does not write `wiki-agent-trigger.json`",
        "does not write or replace `wiki-ingest-record.json`",
    ]:
        assert phrase in combined


def test_check_wiki_supports_layered_checks_and_completion_reports():
    check = _read(PUBLIC_SKILL / "workflows" / "check-wiki.md")
    workflow_doc = _read(PLUGIN / "docs" / "workflow.md")

    for text in [check, workflow_doc]:
        for phrase in [
            "Quick check",
            "Targeted check",
            "Full check",
            "Quick + Targeted",
            "systemic link/tag chaos",
            "graph.json",
            "app.json",
            "userIgnoreFilters",
            "visible formal",
            "broken wikilinks",
        ]:
            assert phrase in text

    for phrase in [
        "Fast Graph Triage",
        "graph.json.search",
        "Markdown scan",
        "close/reopen Graph tab",
        "graph.json.search == \"\"",
        "Completion Report",
        "pages created or updated",
        "links/tags/aliases repaired",
        "tracking files updated",
        "QMD refreshed / skipped / failed with fallback",
        "remaining risks",
        "next Paper Source/Paper Wiki action",
    ]:
        assert phrase in check


def test_zotero_status_workflow_is_read_only_and_human_readable():
    workflow = _read(PUBLIC_SKILL / "workflows" / "zotero-status.md")
    skill = _read(PUBLIC_SKILL / "SKILL.md")
    workflow_doc = _read(PLUGIN / "docs" / "workflow.md")
    structure = _read(PLUGIN / "docs" / "structure.md")
    metadata = _read(PUBLIC_SKILL / "agents" / "openai.yaml")

    for phrase in [
        "read-only by default",
        "does not write formal pages",
        "_meta/reference-index.json",
        "references.bib",
        "Zotero-only",
        "top 20",
        "paper-wiki-zotero-dry-run-v1",
        "writes_performed=false",
        "selected target mismatch",
    ]:
        assert phrase in workflow
    assert "zotero-status.md" in skill
    assert "Zotero 状态/dry-run" in metadata
    assert "read-only Zotero status/dry-run" in workflow_doc
    assert "zotero_status.py" in structure


def test_update_wiki_has_controlled_link_repair_mechanism():
    update = _read(PUBLIC_SKILL / "workflows" / "update-wiki.md")

    for phrase in [
        "Obsidian Graph Visibility Repair",
        "关系图谱出错",
        "graph only index",
        "set the global `search` value to `\"\"`",
        "merge `userIgnoreFilters`",
        "Markdown formal graph scan",
        "Do not use link repair to compensate for a bad Obsidian graph search filter",
        "Scan formal pages",
        "canonical page map",
        "alias map",
        "broken wikilinks",
        "orphan pages",
        "duplicate pages",
        "relationship drift",
        "repair plan",
        "small batches",
        "staging patch",
        "rerun the post-task check",
    ]:
        assert phrase in update


def test_paper_wiki_formal_page_rewrite_is_graph_aware_transaction():
    routing = _load_paper_wiki_routing()
    skill = _read(PUBLIC_SKILL / "SKILL.md")
    standard = _read(PLUGIN / "rules" / "wiki-writing-standard.md")
    update = _read(PUBLIC_SKILL / "workflows" / "update-wiki.md")
    redo = _read(PUBLIC_SKILL / "workflows" / "redo-extraction.md")
    check = _read(PUBLIC_SKILL / "workflows" / "check-wiki.md")

    for phrase in ["重写某页", "重写页面", "rewrite formal page", "rewrite page"]:
        assert phrase in skill
        assert phrase in routing["routes"]["update_wiki"]["triggers"]

    for text in [standard, update, redo]:
        for phrase in [
            "graph-aware rewrite",
            "material rewrite",
            "dependent formal pages",
            "reverse dependencies",
            "references/ pages are evidence source nodes",
            "concepts/",
            "derivations/",
            "experiments/",
            "synthesis/",
            "reports/",
            "opportunities/",
            "final-source-review.json",
            "wiki-ingest-record.json",
            "manifest or `.manifest.json`",
            "index.md",
            "log.md",
            "hot.md",
            "qmd update",
            "qmd embed",
        ]:
            assert phrase in text

    for phrase in [
        "Claim/evidence boundary changes",
        "Formula or figure/table evidence changes",
        "Evidence-tier changes",
        "Relationship or reusable-knowledge changes",
        "Hash/provenance drift",
    ]:
        assert phrase in update

    for phrase in [
        "changed pages and their reverse dependencies",
        "sidecar hashes",
        "QMD refresh status",
    ]:
        assert phrase in check


def test_workflows_adapt_upstream_ingest_status_update_and_relink_patterns():
    extract = _read(PUBLIC_SKILL / "workflows" / "extract-papers.md")
    check = _read(PUBLIC_SKILL / "workflows" / "check-wiki.md")
    update = _read(PUBLIC_SKILL / "workflows" / "update-wiki.md")
    provenance = _read(PUBLIC_SKILL / "references" / "page-provenance.md")

    for phrase in [
        "distill and integrate",
        "existing related pages",
        "manifest",
        "index.md",
        "log.md",
        "hot.md",
        "relationships:",
    ]:
        assert phrase in extract

    for phrase in [
        "What to Do Next",
        "pending Paper Source handoffs",
        "orphan",
        "broken wikilinks",
        "staged writes",
        "provenance gaps",
    ]:
        assert phrase in check

    for phrase in [
        "cross-linker",
        "tag-taxonomy",
        "wiki-lint",
        "missing wikilinks",
        "aliases",
        "one confirmation",
    ]:
        assert phrase in update

    for phrase in ["relationships:", "source-grounded", "unsupported"]:
        assert phrase in provenance


def test_paper_wiki_enforces_ar9av_style_wiki_writing_standard():
    standard_path = PLUGIN / "rules" / "wiki-writing-standard.md"
    standard = _read(standard_path)
    skill = _read(PUBLIC_SKILL / "SKILL.md")
    extract = _read(PUBLIC_SKILL / "workflows" / "extract-papers.md")
    check = _read(PUBLIC_SKILL / "workflows" / "check-wiki.md")
    update = _read(PUBLIC_SKILL / "workflows" / "update-wiki.md")

    assert "../../rules/wiki-writing-standard.md" in skill
    for text in [extract, check, update]:
        assert "../../../rules/wiki-writing-standard.md" in text

    for phrase in [
        "Do not summarize papers in isolation",
        "merge before create",
        "page template",
        "frontmatter",
        "title:",
        "category:",
        "page_family:",
        "tags:",
        "aliases:",
        "relationships:",
        "sources:",
        "summary:",
        "provenance:",
        "base_confidence:",
        "lifecycle:",
        "lifecycle_changed:",
        "tier:",
        "created:",
        "updated:",
        "证据钩子",
        "核心机制",
        "Provenance",
        "references-page-anatomy.md",
        "evidence/",
        "manifest",
        "index.md",
        "log.md",
        "hot.md",
        "orphan",
        "broken wikilinks",
        "relationship issues",
        "staged writes",
        "final-source-review.json",
        "record-wiki-ingest",
    ]:
        assert phrase in standard


def test_paper_wiki_supports_single_and_batch_redo_deep_extraction():
    skill = _read(PUBLIC_SKILL / "SKILL.md")
    redo = _read(PUBLIC_SKILL / "workflows" / "redo-extraction.md")
    metadata = _read(PUBLIC_SKILL / "agents" / "openai.yaml")

    assert "workflows/redo-extraction.md" in skill
    for phrase in ["重做", "重新提取", "更详细", "批量", "redo", "deep extraction"]:
        assert phrase in skill
        assert phrase in redo or phrase in metadata

    for phrase in [
        "single paper",
        "batch",
        "source reread",
        "MinerU Markdown",
        "images",
        "PDF",
        "formula-index.json",
        "figure-index.json",
        "fallback",
        "compare existing pages",
        "staged patch",
        "one confirmation",
        "final-source-review.json",
        "record-wiki-ingest",
        "Do not write human approval",
    ]:
        assert phrase in redo


def test_paper_wiki_uses_title_display_pdf_links_in_sources_and_body():
    standard = _read(PLUGIN / "rules" / "wiki-writing-standard.md")
    frontmatter = _read(PLUGIN / "rules" / "formal-page-frontmatter.md")
    provenance = _read(PUBLIC_SKILL / "references" / "page-provenance.md")
    extract = _read(PUBLIC_SKILL / "workflows" / "extract-papers.md")
    source_linkage = _read(PAPER_SOURCE_PLUGIN / "docs" / "paper-source-linkage.md")
    source_structure = _read(PAPER_SOURCE_PLUGIN / "docs" / "structure.md")
    source_changelog = _read(PAPER_SOURCE_PLUGIN / "docs" / "CHANGELOG.md")

    for text in [standard, frontmatter, provenance, extract]:
        assert "obsidian://open?vault=" in text
        assert "_paper_source/raw/<slug>/paper.pdf" in text
        assert "papers/<slug>" not in text
        assert "[[_paper_source/raw/<slug>/paper.pdf|<slug>]]" not in text
        assert "title-display" in text or "source paper title" in text
        assert "Do not write `[[...]]` wikilinks to `_paper_source/`" in text
        assert "not `原论文 PDF`" in text
    for text in [source_linkage, source_structure, source_changelog]:
        assert "_paper_source/raw/<slug>/paper.pdf" in text
        assert "title-display" in text or "source paper title" in text or "标题显示" in text
        assert "_paper_source/raw/papers/<slug>/paper.pdf" not in text
        assert "_paper_source%2Fraw%2Fpapers%2F<slug>%2Fpaper.pdf" not in text
        assert "[[_paper_source/raw/<slug>/paper.pdf|<slug>]]" not in text
    assert "Markdown link" in standard
    assert "[<full paper title>](obsidian://open?vault=<vault>&file=_paper_source%2Fraw%2F<slug>%2Fpaper.pdf)" in standard
    assert "原论文 PDF" in standard
    assert "Plain path text" in standard
    for phrase in ["metadata", "MinerU", "DOI", "arXiv"]:
        assert phrase in standard
    assert "scan-friendly short labels" not in source_changelog
    assert "旧 frontmatter `sources`" not in source_structure


def test_paper_wiki_frontmatter_governance_uses_title_display_sources():
    standard = _read(PLUGIN / "rules" / "wiki-writing-standard.md")
    frontmatter = _read(PLUGIN / "rules" / "formal-page-frontmatter.md")
    anatomy = _read(PUBLIC_SKILL / "references" / "references-page-anatomy.md")
    check = _read(PUBLIC_SKILL / "workflows" / "check-wiki.md")
    workflow_doc = _read(PLUGIN / "docs" / "workflow.md")

    combined = "\n".join([standard, frontmatter, anatomy, check, workflow_doc])
    for phrase in [
        "paper source entry list",
        "canonical source PDF",
        "source paper title",
        "title-display source PDF links",
        "source_id:",
        "use the paper title as the clickable text, not `原论文 PDF`",
        "frontmatter `provenance` is a compact status summary",
        "detailed source bundle paths belong in the body `## Provenance` block or sidecar",
        "Old `lifecycle: review-needed` pages are legacy repair inputs",
        "Do not add `review_status`",
    ]:
        assert phrase in combined
    assert "source_pdf:" not in combined
    assert "frontmatter `sources:` must stay scan-friendly" not in combined


def test_paper_wiki_evidence_taxonomy_matches_current_vault_tags():
    standard = _read(PLUGIN / "rules" / "wiki-writing-standard.md")
    frontmatter = _read(PLUGIN / "rules" / "formal-page-frontmatter.md")
    anatomy = _read(PUBLIC_SKILL / "references" / "references-page-anatomy.md")
    survey = _read(PUBLIC_SKILL / "references" / "survey-page-anatomy.md")

    combined = "\n".join([standard, frontmatter, anatomy, survey])
    for tag in [
        "evidence/simulation",
        "evidence/hardware-in-the-loop",
        "evidence/pool-trial",
        "evidence/lake-trial",
        "evidence/real-robot-lab",
        "evidence/sea-trial",
        "evidence/real-data-driven-simulation",
        "evidence/literature-review",
    ]:
        assert tag in combined
    assert "evidence/field-test" in combined
    assert "Do not use `evidence/field-test`" in combined


def test_internal_snapshot_and_source_trees_are_excluded_from_formal_indexing():
    standard = _read(PLUGIN / "rules" / "wiki-writing-standard.md")
    check = _read(PUBLIC_SKILL / "workflows" / "check-wiki.md")
    update = _read(PUBLIC_SKILL / "workflows" / "update-wiki.md")
    workflow_doc = _read(PLUGIN / "docs" / "workflow.md")

    combined = "\n".join([standard, check, update, workflow_doc])
    for phrase in [
        "_paper_source/meta/formal-page-snapshots",
        "premature-formal-pages",
        "must stay outside the formal graph",
        "must stay outside QMD",
        "page_family/category/lifecycle markers under underscore roots are audit copies",
        "not formal pages",
    ]:
        assert phrase in combined


def test_paper_wiki_active_docs_use_paper_source_root_as_primary_path():
    ask = _read(PUBLIC_SKILL / "workflows" / "ask-wiki.md")
    check = _read(PUBLIC_SKILL / "workflows" / "check-wiki.md")
    update = _read(PUBLIC_SKILL / "workflows" / "update-wiki.md")
    page_family = _read(PUBLIC_SKILL / "references" / "page-family-contract.md")
    anatomy = _read(PUBLIC_SKILL / "references" / "references-page-anatomy.md")
    upstream = _read(PUBLIC_SKILL / "references" / "upstream-obsidian-wiki-map.md")

    assert "Use `_paper_source/raw` as primary source evidence" in ask
    assert "core `_paper_source` roots" in check
    assert "using `_paper_source/staging/papers/*/wiki-ingest-brief.json` as the only Paper Source-to-Paper Wiki handoff contract" in check
    assert "Forbidden formal roots are `_paper_source/`, `_raw/`, `_staging/`, `_runs/`, `_quarantine/`, and `.obsidian/`" in page_family
    assert "forbidden internal links from formal pages into `_paper_source/` or other internal folders" in upstream
    assert "forbidden internal links" in update
    assert "file=_paper_source%2Fraw%2F<slug>%2Fpaper.pdf" in anatomy
    old_root = "_" + "".join(["e", "p", "i"])
    assert old_root not in "\n".join([ask, check, update, page_family, anatomy, upstream])
    assert "full source map remains in `_paper_source/raw/<slug>/mineru/*`" in anatomy
    assert "file:///D:/paper-research-wiki/_paper_source/raw/<slug>/mineru/images/<hash>.jpg" in anatomy


def test_paper_wiki_scopes_reference_single_source_separately_from_synthesis_pages():
    standard = _read(PLUGIN / "rules" / "wiki-writing-standard.md")
    frontmatter = _read(PLUGIN / "rules" / "formal-page-frontmatter.md")
    provenance = _read(PUBLIC_SKILL / "references" / "page-provenance.md")
    extract = _read(PUBLIC_SKILL / "workflows" / "extract-papers.md")

    for text in [standard, frontmatter, provenance, extract]:
        assert "references/" in text
        assert (
            "exactly one source PDF link" in text
            or "exactly one Markdown link to the canonical source PDF" in text
        )
    for text in [standard, frontmatter, provenance, extract]:
        for family in ["concepts/", "derivations/", "experiments/", "synthesis/", "reports/", "opportunities/"]:
            assert family in text
        assert "one or more title-display source PDF links" in text
    assert "same frontmatter contract" not in standard


def test_formal_frontmatter_required_fields_match_validation_mirrors():
    from paper_source.wiki_contracts import FORMAL_FRONTMATTER_REQUIRED_FIELDS

    standard = _read(PLUGIN / "rules" / "wiki-writing-standard.md")
    frontmatter = _read(PLUGIN / "rules" / "formal-page-frontmatter.md")
    source_contracts = _read(PAPER_SOURCE_PLUGIN / "scripts" / "build" / "paper_source" / "wiki_contracts.py")
    source_linkage = _read(PAPER_SOURCE_PLUGIN / "docs" / "paper-source-linkage.md")
    source_workflow = _read(PAPER_SOURCE_PLUGIN / "docs" / "workflow.md")
    source_structure = _read(PAPER_SOURCE_PLUGIN / "docs" / "structure.md")
    source_wiki_setup = _read(PAPER_SOURCE_PLUGIN / "skills" / "wiki-setup" / "SKILL.md")

    assert _required_fields_from_canonical_standard(standard) == list(FORMAL_FRONTMATTER_REQUIRED_FIELDS)
    assert _required_fields_from_focused_frontmatter_rule(frontmatter) == list(FORMAL_FRONTMATTER_REQUIRED_FIELDS)

    for text in [
        frontmatter,
        source_contracts,
        source_linkage,
        source_workflow,
        source_structure,
        source_wiki_setup,
    ]:
        assert "validation mirror" in text
    assert "canonical human-readable contract" in standard


def test_paper_wiki_supports_frontmatter_only_github_metadata_repair():
    standard = _read(PLUGIN / "rules" / "wiki-writing-standard.md")
    update = _read(PUBLIC_SKILL / "workflows" / "update-wiki.md")
    workflow_doc = _read(PLUGIN / "docs" / "workflow.md")

    for phrase in [
        "Frontmatter-Only Metadata Repair",
        "verified `github:` property",
        "Preserve `sources:` as title-display Markdown links to the canonical source PDFs",
        "do not add GitHub, DOI, arXiv, README, metadata, MinerU paths, figure paths, plain/relative PDF paths",
        "Do not automatically run the full graph-aware rewrite path",
        "Escalate to Graph-Aware Rewrite only if the metadata changes a claim",
    ]:
        assert phrase in update

    for phrase in [
        "repository links belong in a separate frontmatter property such as `github:`",
        "not in `sources:`",
        "frontmatter-only metadata repair",
        "targeted static repository verification",
        "whether the code was run locally",
    ]:
        assert phrase in standard

    for phrase in [
        "Frontmatter-only metadata repair",
        "verified `github:` property",
        "preserve `sources:` as title-display Markdown links to canonical source PDFs",
        "Do not trigger graph-aware rewrite",
        "paper-wiki-record-request.json",
        "record-wiki-ingest",
        "metadata-only path",
    ]:
        assert phrase in workflow_doc


def test_references_page_anatomy_keeps_graph_integration_as_quality_rule_not_heading():
    anatomy = _read(PUBLIC_SKILL / "references" / "references-page-anatomy.md")
    style = _read(PLUGIN / "skills" / "paper-wiki-language" / "references" / "style-guide.md")

    for canonical in [
        "证据钩子",
        "原文与证据入口",
        "问题设定",
        "核心机制",
        "实验设置与证据边界",
        "局限与未覆盖问题",
        "Provenance",
    ]:
        assert canonical in anatomy

    assert "## 在知识图谱中的位置" not in anatomy
    assert "在知识图谱中的位置 / Provenance" not in style
    assert "graph integration" in anatomy
    assert "named sibling pages" in anatomy
    assert "natural body links" in anatomy
    assert "not a mandatory heading" in anatomy


def test_references_page_anatomy_allows_current_approved_heading_aliases():
    anatomy = _read(PUBLIC_SKILL / "references" / "references-page-anatomy.md")
    style = _read(PLUGIN / "skills" / "paper-wiki-language" / "references" / "style-guide.md")

    for alias in [
        "Evidence Hooks",
        "原论文 PDF",
        "原论文与证据",
        "原论文与证据入口",
        "实验设置和证据边界",
        "局限和未覆盖问题",
        "与现有图谱的关系",
    ]:
        assert alias in anatomy
    assert "accepted aliases" in anatomy
    assert "preferred for new writes" in style


def test_references_page_anatomy_requires_source_map_formula_chain_and_figure_cards():
    anatomy = _read(PUBLIC_SKILL / "references" / "references-page-anatomy.md")

    for phrase in [
        "Source-map-first writing",
        "MinerU Markdown is the primary formula and notation source",
        "Only fall back to the PDF, formula-index.json, figure-index.json, or image evidence",
        "reader/critic artifacts are secondary aids",
        "Do not expose the full source map",
        "Formula reasoning chain",
        "premise -> equation -> variable definitions -> guarantee -> next step -> baseline contrast",
        "原文未明确说明",
        "Evidence figure card",
        "Placed near:",
        "Source:",
        "中文图注:",
        "Reading note:",
        "Reviewer-style boundary check",
        "originality",
        "scientific importance",
        "technical soundness",
        "not assessable",
    ]:
        assert phrase in anatomy
    assert "MinerU Markdown / TeX / images / manifest" not in anatomy


def test_paper_wiki_keeps_obsidian_syntax_paper_evidence_and_vault_governance_separate():
    skill = _read(PUBLIC_SKILL / "SKILL.md")
    standard = _read(PLUGIN / "rules" / "wiki-writing-standard.md")
    frontmatter = _read(PLUGIN / "rules" / "formal-page-frontmatter.md")
    structure = _read(PLUGIN / "docs" / "structure.md")
    workflow = _read(PLUGIN / "docs" / "workflow.md")
    artifact_contract = _read(PUBLIC_SKILL / "references" / "paper-source-artifact-contract.md")

    combined = "\n".join([skill, standard, frontmatter, structure, workflow, artifact_contract])
    for phrase in [
        "Governance Layers",
        "Obsidian syntax layer",
        "Paper Wiki paper-evidence layer",
        "Local vault governance layer",
        "kepano/obsidian-skills",
        "YAML properties/frontmatter",
        "wikilinks",
        "embeds",
        "callouts",
        "Markdown links",
        "source-map-grounded paper claims",
        "formal page relationships",
        "target vault `AGENTS.md` and `_meta/*`",
        "Sample vaults and upstream wiki repositories are references, not hard schemas",
    ]:
        assert phrase in combined

    assert "Native TeX is not required" in artifact_contract
    assert "Missing native TeX is normal" in skill
    for text in [skill, standard, artifact_contract]:
        assert "MinerU Markdown" in text
        assert "missing, wrong, ambiguous, or insufficient" in text


def test_paper_wiki_defines_formal_knowledge_maintenance_beyond_page_writing():
    skill = _read(PUBLIC_SKILL / "SKILL.md")
    standard = _read(PLUGIN / "rules" / "wiki-writing-standard.md")
    update = _read(PUBLIC_SKILL / "workflows" / "update-wiki.md")
    redo = _read(PUBLIC_SKILL / "workflows" / "redo-extraction.md")

    combined = "\n".join([skill, standard, update, redo])
    for phrase in [
        "formal knowledge maintenance layer",
        "formal page content relationships",
        "content relationship maintenance",
        "claim staleness",
        "split or merge pages",
        "reverse dependencies",
        "evidence-tier drift",
        "derived concepts",
        "derivations",
        "synthesis",
    ]:
        assert phrase in combined


def test_skill_ui_metadata_uses_single_public_skill():
    metadata = _read(PUBLIC_SKILL / "agents" / "openai.yaml")

    assert "display_name: \"Paper Wiki\"" in metadata
    assert "$paper-research-wiki" in metadata
    for phrase in ["提取", "检测", "更新", "沉淀", "重做", "重link", "Zotero"]:
        assert phrase in metadata


def test_paper_wiki_short_aliases_are_natural_language_only():
    routing = _read(PLUGIN / "skills" / "routing.yaml")
    skill = _read(PUBLIC_SKILL / "SKILL.md")
    metadata = _read(PUBLIC_SKILL / "agents" / "openai.yaml")

    for phrase in ["Paper Wiki", "PW", "用 PW 沉淀到 wiki", "用 PW 问 wiki", "Paper Source"]:
        assert phrase in "\n".join([routing, skill, metadata])

    assert ("$" + "PS") not in routing
    assert ("$" + "PW") not in routing
    assert ("name: " + "ps") not in routing.lower()
    assert ("name: " + "pw") not in routing.lower()


def test_paper_wiki_user_docs_use_paper_wiki_and_paper_source_stage2_names():
    workflow = _read(PLUGIN / "docs" / "workflow.md")
    structure = _read(PLUGIN / "docs" / "structure.md")
    integration = _read(PLUGIN / "docs" / "paper-source-integration.md")
    combined = "\n".join([workflow, structure, integration])

    for phrase in [
        "Paper Wiki",
        "Paper Source",
        "PW",
        "PS",
        "machine-facing",
        "`paper-wiki`",
        "`paper-source`",
        "Historical aliases are not Paper Wiki user entrypoints",
    ]:
        assert phrase in combined

    for phrase in [
        "Paper Source `wiki-setup`",
        "wiki-ingest-brief.json",
        "paper-wiki-record-request.json",
    ]:
        assert phrase in combined


def test_current_names_do_not_keep_old_aliases_as_user_contracts():
    files = [
        PLUGIN / "skills" / "routing.yaml",
        PLUGIN / "skills" / "paper-research-wiki" / "SKILL.md",
        PLUGIN / "docs" / "paper-source-integration.md",
        PAPER_SOURCE_PLUGIN / "skills" / "routing.yaml",
        PAPER_SOURCE_PLUGIN / "skills" / "paper-source-paper-deposition" / "SKILL.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)

    for phrase in [
        "wiki-ingest-brief.json",
        "paper-research-wiki",
        "Historical aliases are not user entrypoints",
    ]:
        assert phrase in combined
    old_paper_wiki_alias = "`" + "".join(["p", "r", "w"]) + "`"
    old_paper_source_alias = "`" + "".join(["e", "p", "i"]) + "`"
    assert old_paper_wiki_alias not in combined
    assert old_paper_source_alias not in combined
    assert ("compatibility " + "adapter") not in combined


def test_all_paper_wiki_skills_have_ui_metadata():
    for skill_name in PUBLIC_SKILLS | SUPPORT_SKILLS:
        metadata_path = PLUGIN / "skills" / skill_name / "agents" / "openai.yaml"
        assert metadata_path.exists(), skill_name

        metadata = _load_openai_metadata(metadata_path)
        interface = metadata.get("interface", {})
        assert interface.get("display_name"), skill_name
        short_description = interface.get("short_description", "")
        assert 20 <= len(short_description) <= 80, skill_name
        default_prompt = interface.get("default_prompt", "")
        assert f"${skill_name}" in default_prompt, skill_name
        assert re.search(r"[\u4e00-\u9fff]", default_prompt), skill_name


def test_paper_source_bridge_points_to_plugin_level_experience():
    skill = _read(ROOT / "plugins" / "paper-source" / "skills" / "paper-source-paper-deposition" / "SKILL.md")
    workflow = _read(
        ROOT
        / "plugins"
        / "paper-source"
        / "skills"
        / "paper-source-paper-deposition"
        / "workflows"
        / "formal-wiki-write.md"
    )
    structure = _read(ROOT / "plugins" / "paper-source" / "docs" / "structure.md")
    linkage = _read(ROOT / "plugins" / "paper-source" / "docs" / "paper-source-linkage.md")

    for text in [skill, workflow, structure, linkage]:
        assert "paper-research-wiki" in text
    assert "$paper-research-wiki" in skill
    assert "wiki-ingest-brief.json" in skill
    retired_task = "wiki_" + "deposition_task"
    assert f"Historical `{retired_task}.json` cleanup" in skill
    assert ("compatibility " + "adapter") not in skill
    for text in [skill, workflow]:
        assert "graph-aware rewrite" in text
        assert "$paper-research-wiki" in text


def test_paper_source_handoff_and_paper_wiki_routing_share_canonical_contract():
    wiki_contracts = _read(PAPER_SOURCE_PLUGIN / "scripts" / "build" / "paper_source" / "wiki_contracts.py")
    stage_wiki = _read(PAPER_SOURCE_PLUGIN / "scripts" / "build" / "paper_source" / "stage_wiki.py")
    paper_source_routing = _read(PAPER_SOURCE_PLUGIN / "skills" / "routing.yaml")
    paper_wiki_routing = _read(PLUGIN / "skills" / "routing.yaml")
    paper_wiki_skill = _read(PUBLIC_SKILL / "SKILL.md")
    check_workflow = _read(PUBLIC_SKILL / "workflows" / "check-wiki.md")
    workflow_doc = _read(PLUGIN / "docs" / "workflow.md")

    assert 'PAPER_WIKI_CANONICAL_SKILL = "paper-research-wiki"' in wiki_contracts
    assert "PAPER_WIKI_CANONICAL_SKILL" in stage_wiki
    assert "first as the canonical paper wiki layer" in stage_wiki
    retired_task = "wiki_" + "deposition_task"
    assert retired_task in stage_wiki

    deposition_match = re.search(
        r"(?ms)^  paper_source_paper_deposition:\n(?P<body>.*?)(?=^  [a-z0-9_]+:|\Z)",
        paper_source_routing,
    )
    assert deposition_match
    deposition_route = deposition_match.group("body")
    assert "category: maintenance" in deposition_route
    assert "skill: paper-source-paper-deposition/SKILL.md" in deposition_route
    assert "$paper-research-wiki" in deposition_route

    combined_paper_wiki_boundary = "\n".join([paper_wiki_routing, paper_wiki_skill, check_workflow, workflow_doc])
    assert "missing vault structure" in combined_paper_wiki_boundary
    assert "Paper Source `wiki-setup`" in combined_paper_wiki_boundary
    assert "does not initialize" in combined_paper_wiki_boundary
    assert "does not reset" in combined_paper_wiki_boundary


def test_paper_wiki_defers_vault_bootstrap_to_paper_source_wiki_setup():
    skill = _read(PUBLIC_SKILL / "SKILL.md")
    check_workflow = _read(PUBLIC_SKILL / "workflows" / "check-wiki.md")
    extract_workflow = _read(PUBLIC_SKILL / "workflows" / "extract-papers.md")
    integration = _read(PLUGIN / "docs" / "paper-source-integration.md")
    combined = "\n".join([skill, check_workflow, extract_workflow, integration])

    assert "Paper Source `wiki-setup`" in combined
    assert "does not initialize" in integration
    assert "does not reset" in integration
    assert "missing vault structure" in combined


def test_paper_wiki_artifact_contract_marks_task_deprecated():
    contract = _read(PUBLIC_SKILL / "references" / "paper-source-artifact-contract.md")
    retired_task = "wiki_" + "deposition_task"

    assert "wiki-ingest-brief.json" in contract
    assert f"{retired_task}.json" not in contract


def test_paper_wiki_paper_source_artifact_contract_is_brief_first():
    contract = _read(PUBLIC_SKILL / "references" / "paper-source-artifact-contract.md")
    extract = _read(PUBLIC_SKILL / "workflows" / "extract-papers.md")
    check = _read(PUBLIC_SKILL / "workflows" / "check-wiki.md")
    integration = _read(PLUGIN / "docs" / "paper-source-integration.md")
    combined = "\n".join([contract, extract, check, integration])
    retired_task = "wiki_" + "deposition_task"

    assert "canonical handoff" in contract
    assert "wiki-ingest-brief.json" in contract
    assert "Locate `_paper_source/staging/papers/*/wiki-ingest-brief.json`" in extract
    assert f"{retired_task}.json" not in contract
    assert "compatibility artifact" not in combined


def test_wiki_writing_standard_declares_itself_canonical():
    rule = _read(PLUGIN / "rules" / "wiki-writing-standard.md")

    assert "canonical" in rule.lower() or "唯一权威" in rule
    assert "page" in rule.lower() and "frontmatter" in rule.lower()


def test_ask_wiki_notes_paper_source_cli_is_same_source_fallback():
    ask = _read(PUBLIC_SKILL / "workflows" / "ask-wiki.md")

    assert "wiki-ask" in ask
    assert ("fallback" in ask.lower()) or ("程序化" in ask) or ("同源" in ask)
