import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "plugins" / "PRW"
EPI_PLUGIN = ROOT / "plugins" / "epi"
PUBLIC_SKILL = PLUGIN / "skills" / "paper-research-wiki"
MARKETPLACES = [
    ROOT / "marketplace.json",
    ROOT / ".agents" / "plugins" / "marketplace.json",
]
WORKFLOWS = {
    "ask-wiki.md",
    "extract-papers.md",
    "check-wiki.md",
    "update-wiki.md",
    "redo-extraction.md",
}
PUBLIC_SKILLS = {"paper-research-wiki"}
SUPPORT_SKILLS = {"paper-wiki-language"}
REFERENCES = {
    "epi-artifact-contract.md",
    "page-provenance.md",
    "page-family-contract.md",
    "references-page-anatomy.md",
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
    "_epi/",
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


def _load_prw_routing():
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


def test_plugin_manifest_exposes_simple_user_prompts():
    manifest = _read_json(PLUGIN / ".codex-plugin" / "plugin.json")

    assert manifest["name"] == "prw"
    assert manifest["version"] == "0.2.1"
    assert manifest["skills"] == "./skills/"
    assert manifest["interface"]["displayName"] == "Paper Research Wiki"
    assert "academic paper knowledge" in manifest["description"]
    assert "source-map-grounded" in manifest["description"]
    assert "formula reasoning chains" in manifest["interface"]["longDescription"]
    assert "evidence figure cards" in manifest["interface"]["longDescription"]
    assert "link repair" in manifest["interface"]["longDescription"]
    assert "QMD-compatible" in manifest["interface"]["longDescription"]
    assert "post-task check" in manifest["interface"]["longDescription"]
    assert (
        manifest["interface"]["shortDescription"]
        == "v0.2.1 | Brief-first PRW deposition, ask, checks, update, relink, redo, record requests."
    )
    for phrase in ["deposition", "ask", "checks", "update", "relink", "redo"]:
        assert phrase in manifest["interface"]["shortDescription"]
    prompt_text = "\n".join(manifest["interface"]["defaultPrompt"])
    for phrase in ["提取", "提问", "检测", "更新", "沉淀", "EPI", "link", "QMD"]:
        assert phrase in prompt_text


def test_epi_manifest_describes_brief_first_prw_boundary():
    manifest = _read_json(EPI_PLUGIN / ".codex-plugin" / "plugin.json")

    assert manifest["version"] == "0.2.1"
    assert (
        manifest["description"]
        == "Discover, acquire, parse, stage, approve, hand off, query, and record academic paper knowledge for an EPI-compatible PRW wiki."
    )
    assert (
        manifest["interface"]["shortDescription"]
        == "v0.2.1 | Find, vet, route sources, OA-acquire, brief-first hand off to PRW, wiki-ask, and record PRW requests."
    )


def test_marketplaces_register_paper_research_wiki():
    for marketplace_path in MARKETPLACES:
        marketplace = _read_json(marketplace_path)
        entries = {entry["name"]: entry for entry in marketplace["plugins"]}

        assert "prw" in entries, marketplace_path
        entry = entries["prw"]
        assert entry["source"] == {
            "source": "local",
            "path": "./plugins/PRW",
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
    assert "formal PRW/EPI" in language_skill
    assert "Language Gate" in language_skill
    assert "references/style-guide.md" in language_skill


def test_prw_all_skill_entrypoints_stay_thin():
    for skill_name in PUBLIC_SKILLS | SUPPORT_SKILLS:
        skill_path = PLUGIN / "skills" / skill_name / "SKILL.md"
        assert _skill_body_line_count(skill_path) <= 90, skill_name


def test_prw_support_skill_entrypoints_stay_thin_and_route_to_style_guide():
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


def test_public_skill_routes_natural_epi_deposition_actions():
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


def test_prw_skill_routing_manifest_matches_public_workflows():
    routing_path = PLUGIN / "skills" / "routing.yaml"
    assert routing_path.exists()

    routing = _load_prw_routing()
    assert routing["schema_version"] == "prw-skill-routing-v1"
    assert routing["source_of_truth"] == "skills/routing.yaml"
    assert len(routing["always_read"]) <= 3
    assert "paper-research-wiki/references/upstream-obsidian-wiki-map.md" not in routing["always_read"]
    assert "../rules/wiki-writing-standard.md" in routing["always_read"]

    routes = routing["routes"]
    assert set(routes) == {"extract_papers", "check_wiki", "ask_wiki", "redo_extraction", "update_wiki", "language_gate"}

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

    skill = _read(PUBLIC_SKILL / "SKILL.md")
    assert "../routing.yaml" in skill
    assert "routing manifest" in skill

    assert "paper-wiki-language/references/style-guide.md" in routes["language_gate"].get("references", [])


def test_prw_routes_read_only_wiki_questions_to_ask_workflow():
    routing = _load_prw_routing()
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
    integration_doc = _read(PLUGIN / "docs" / "epi-integration.md")
    combined = "\n".join([workflow, routing, workflow_doc, structure_doc, integration_doc])

    for phrase in [
        "read-only",
        "no `log.md`",
        "do not write `log.md`",
        "do not write formal pages",
        "do not refresh QMD",
        "do not write EPI artifacts",
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
    assert "prw-record-request.json" in integration_doc
    assert "ask-wiki does not write `prw-record-request.json`" in integration_doc


def test_public_skill_references_internal_contract_files():
    skill = _read(PUBLIC_SKILL / "SKILL.md")

    for reference in REFERENCES:
        assert f"references/{reference}" in skill
        path = PUBLIC_SKILL / "references" / reference
        assert path.exists(), reference
        assert path.read_text(encoding="utf-8").strip(), reference


def test_public_skill_defaults_epi_wiki_requests_to_deposition():
    skill = _read(PUBLIC_SKILL / "SKILL.md")

    for phrase in [
        "EPI",
        "ready",
        "preflight",
        "沉淀",
        "wiki-ingest-brief.json",
        "legacy `wiki_deposition_task.json`",
        "wiki_deposition_task.json",
        "workflows/extract-papers.md",
        "workflows/check-wiki.md",
    ]:
        assert phrase in skill


def test_required_docs_and_rules_exist():
    required = [
        "AGENTS.md",
        "docs/workflow.md",
        "docs/structure.md",
        "docs/epi-integration.md",
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


def test_epi_integration_docs_name_handoff_and_record_contracts():
    text = _read(PLUGIN / "docs" / "epi-integration.md")

    for phrase in [
        "canonical handoff",
        "legacy compatibility",
        "wiki_deposition_task.json",
        "wiki-ingest-brief.json",
        "final-source-review.json",
        "record-wiki-ingest",
        "paper-gate",
        "human approval",
    ]:
        assert phrase in text


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
        "normal PRW runs",
        "local PRW workflows",
        "upstream repository only when maintaining PRW",
    ]:
        assert phrase in text


def test_prw_internalizes_link_repair_qmd_and_post_task_checks():
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


def test_prw_declares_closed_loop_boundary_and_completion_definition():
    skill = _read(PUBLIC_SKILL / "SKILL.md")
    standard = _read(PLUGIN / "rules" / "wiki-writing-standard.md")
    workflow_doc = _read(PLUGIN / "docs" / "workflow.md")
    epi_integration = _read(PLUGIN / "docs" / "epi-integration.md")

    for text in [skill, workflow_doc]:
        assert "Check -> Diagnose -> Plan -> Act -> Verify -> Refresh -> Record -> Next" in text

    for text in [skill, standard, workflow_doc]:
        assert (
            "A PRW task is not complete until formal pages, tracking files, graph links, "
            "taxonomy, provenance, language gate, QMD freshness, and EPI record readiness "
            "have been checked or explicitly reported as skipped with reason."
        ) in text

    for text in [skill, workflow_doc, epi_integration]:
        for phrase in [
            "PRW owns",
            "EPI owns",
            "paper discovery",
            "MinerU parsing",
            "paper-gate",
            "human approval",
            "record-wiki-ingest",
            "final-source-review.json",
        ]:
            assert phrase in text


def test_prw_does_not_claim_to_refresh_epi_record_files():
    standard = _read(PLUGIN / "rules" / "wiki-writing-standard.md")
    update = _read(PUBLIC_SKILL / "workflows" / "update-wiki.md")
    redo = _read(PUBLIC_SKILL / "workflows" / "redo-extraction.md")
    extract = _read(PUBLIC_SKILL / "workflows" / "extract-papers.md")
    check = _read(PUBLIC_SKILL / "workflows" / "check-wiki.md")
    integration = _read(PLUGIN / "docs" / "epi-integration.md")

    combined = "\n".join([standard, update, redo, extract, check, integration])

    assert "EPI owns human approval records and `record-wiki-ingest`" in combined
    assert "previous `wiki-ingest-record.json`" in combined
    assert "staging/raw `wiki-ingest-record.json`" not in combined
    assert "Refresh manifest or `.manifest.json`, `final-source-review.json`, staging/raw `wiki-ingest-record.json`" not in combined
    assert "PRW records readiness; EPI writes or replaces `wiki-ingest-record.json`" in combined


def test_prw_documents_ask_mode_epi_record_request_handoff():
    standard = _read(PLUGIN / "rules" / "wiki-writing-standard.md")
    extract = _read(PUBLIC_SKILL / "workflows" / "extract-papers.md")
    update = _read(PUBLIC_SKILL / "workflows" / "update-wiki.md")
    redo = _read(PUBLIC_SKILL / "workflows" / "redo-extraction.md")
    integration = _read(PLUGIN / "docs" / "epi-integration.md")
    combined = "\n".join([standard, extract, update, redo, integration])

    for phrase in [
        "prw-record-request.json",
        "schema_version: prw-record-request-v1",
        "automation_mode: ask",
        "record-wiki-ingest --from-prw-request",
        "PRW writes the request artifact; EPI consumes it",
    ]:
        assert phrase in combined

    assert "PRW writes or replaces `wiki-ingest-record.json`" not in combined


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
        ]:
            assert phrase in text

    for phrase in [
        "Completion Report",
        "pages created or updated",
        "links/tags/aliases repaired",
        "tracking files updated",
        "QMD refreshed / skipped / failed with fallback",
        "remaining risks",
        "next EPI/PRW action",
    ]:
        assert phrase in check


def test_update_wiki_has_controlled_link_repair_mechanism():
    update = _read(PUBLIC_SKILL / "workflows" / "update-wiki.md")

    for phrase in [
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


def test_prw_formal_page_rewrite_is_graph_aware_transaction():
    routing = _load_prw_routing()
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
        "pending EPI handoffs",
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


def test_prw_enforces_ar9av_style_wiki_writing_standard():
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


def test_prw_supports_single_and_batch_redo_deep_extraction():
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
        "TeX",
        "images",
        "PDF",
        "compare existing pages",
        "staged patch",
        "one confirmation",
        "final-source-review.json",
        "record-wiki-ingest",
        "do not write human approval",
    ]:
        assert phrase in redo


def test_prw_requires_clickable_source_pdf_links_in_frontmatter():
    standard = _read(PLUGIN / "rules" / "wiki-writing-standard.md")
    frontmatter = _read(PLUGIN / "rules" / "formal-page-frontmatter.md")
    provenance = _read(PUBLIC_SKILL / "references" / "page-provenance.md")
    extract = _read(PUBLIC_SKILL / "workflows" / "extract-papers.md")

    for text in [standard, frontmatter, provenance, extract]:
        # canonical clickable obsidian:// form displayed with the paper title
        assert "obsidian://open?vault=" in text
        # correct PDF path with no stale papers/ segment; legacy wikilink form still accepted
        assert "_epi/raw/<slug>/paper.pdf" in text
        assert "papers/<slug>" not in text
        assert "[[_epi/raw/<slug>/paper.pdf|<slug>]]" in text
    assert "Markdown link" in standard
    assert "原论文 PDF" in standard
    assert "plain path text" in standard
    for phrase in ["metadata", "MinerU", "DOI", "arXiv"]:
        assert phrase in standard


def test_prw_scopes_reference_single_source_separately_from_synthesis_pages():
    standard = _read(PLUGIN / "rules" / "wiki-writing-standard.md")
    frontmatter = _read(PLUGIN / "rules" / "formal-page-frontmatter.md")
    provenance = _read(PUBLIC_SKILL / "references" / "page-provenance.md")
    extract = _read(PUBLIC_SKILL / "workflows" / "extract-papers.md")

    for text in [standard, frontmatter, provenance, extract]:
        assert "references/ pages" in text
        assert "exactly one clickable original-paper PDF link" in text
    for text in [standard, frontmatter, extract]:
        assert "concepts/, derivations/, experiments/, synthesis/, reports/, and opportunities/" in text
        assert "one or more clickable original-paper PDF links" in text
    assert "same frontmatter contract" not in standard


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
        "MinerU Markdown / TeX / images / manifest",
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


def test_skill_ui_metadata_uses_single_public_skill():
    metadata = _read(PUBLIC_SKILL / "agents" / "openai.yaml")

    assert "display_name: \"Paper Research Wiki\"" in metadata
    assert "$paper-research-wiki" in metadata
    for phrase in ["提取", "检测", "更新", "沉淀", "重做", "重link"]:
        assert phrase in metadata


def test_all_prw_skills_have_ui_metadata():
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


def test_epi_bridge_points_to_plugin_level_experience():
    skill = _read(ROOT / "plugins" / "epi" / "skills" / "epi-paper-deposition" / "SKILL.md")
    workflow = _read(
        ROOT
        / "plugins"
        / "epi"
        / "skills"
        / "epi-paper-deposition"
        / "workflows"
        / "formal-wiki-write.md"
    )
    structure = _read(ROOT / "plugins" / "epi" / "docs" / "structure.md")
    linkage = _read(ROOT / "plugins" / "epi" / "docs" / "epi-linkage.md")

    for text in [skill, workflow, structure, linkage]:
        assert "paper-research-wiki" in text
    assert "$paper-research-wiki" in skill
    assert "wiki-ingest-brief.json" in skill
    assert "legacy `wiki_deposition_task.json`" in skill
    assert "compatibility adapter" in skill
    for text in [skill, workflow]:
        assert "graph-aware rewrite" in text
        assert "$paper-research-wiki" in text


def test_epi_handoff_and_prw_routing_share_canonical_contract():
    wiki_contracts = _read(EPI_PLUGIN / "scripts" / "build" / "epi" / "wiki_contracts.py")
    stage_wiki = _read(EPI_PLUGIN / "scripts" / "build" / "epi" / "stage_wiki.py")
    epi_routing = _read(EPI_PLUGIN / "skills" / "routing.yaml")
    prw_routing = _read(PLUGIN / "skills" / "routing.yaml")
    prw_skill = _read(PUBLIC_SKILL / "SKILL.md")
    check_workflow = _read(PUBLIC_SKILL / "workflows" / "check-wiki.md")
    workflow_doc = _read(PLUGIN / "docs" / "workflow.md")

    assert 'PRW_CANONICAL_SKILL = "paper-research-wiki"' in wiki_contracts
    assert "PRW_CANONICAL_SKILL" in stage_wiki
    assert "first as the canonical paper wiki layer" in stage_wiki
    assert "wiki_deposition_task" in stage_wiki

    deposition_match = re.search(
        r"(?ms)^  epi_paper_deposition:\n(?P<body>.*?)(?=^  [a-z0-9_]+:|\Z)",
        epi_routing,
    )
    assert deposition_match
    deposition_route = deposition_match.group("body")
    assert "category: compatibility" in deposition_route
    assert "skill: epi-paper-deposition/SKILL.md" in deposition_route
    assert "$paper-research-wiki" in deposition_route

    combined_prw_boundary = "\n".join([prw_routing, prw_skill, check_workflow, workflow_doc])
    assert "missing vault structure" in combined_prw_boundary
    assert "EPI `wiki-setup`" in combined_prw_boundary
    assert "does not initialize" in combined_prw_boundary
    assert "does not reset" in combined_prw_boundary


def test_prw_defers_vault_bootstrap_to_epi_wiki_setup():
    skill = _read(PUBLIC_SKILL / "SKILL.md")
    check_workflow = _read(PUBLIC_SKILL / "workflows" / "check-wiki.md")
    extract_workflow = _read(PUBLIC_SKILL / "workflows" / "extract-papers.md")
    integration = _read(PLUGIN / "docs" / "epi-integration.md")
    combined = "\n".join([skill, check_workflow, extract_workflow, integration])

    assert "EPI `wiki-setup`" in combined
    assert "does not initialize" in integration
    assert "does not reset" in integration
    assert "missing vault structure" in combined


def test_prw_artifact_contract_marks_task_deprecated():
    contract = _read(PUBLIC_SKILL / "references" / "epi-artifact-contract.md")

    assert "wiki-ingest-brief.json" in contract
    assert "wiki_deposition_task.json" in contract
    assert "deprecated" in contract.lower() or "已废弃" in contract


def test_prw_epi_artifact_contract_is_brief_first():
    contract = _read(PUBLIC_SKILL / "references" / "epi-artifact-contract.md")
    extract = _read(PUBLIC_SKILL / "workflows" / "extract-papers.md")
    check = _read(PUBLIC_SKILL / "workflows" / "check-wiki.md")
    integration = _read(PLUGIN / "docs" / "epi-integration.md")
    combined = "\n".join([contract, extract, check, integration])

    assert "canonical handoff" in contract
    assert "wiki-ingest-brief.json" in contract
    assert "wiki_deposition_task.json" in contract
    assert "legacy compatibility" in contract
    assert "Locate `_epi/staging/papers/*/wiki-ingest-brief.json`" in extract
    assert "Do not treat task-only legacy handoffs as ready" in combined


def test_wiki_writing_standard_declares_itself_canonical():
    rule = _read(PLUGIN / "rules" / "wiki-writing-standard.md")

    assert "canonical" in rule.lower() or "唯一权威" in rule
    assert "page" in rule.lower() and "frontmatter" in rule.lower()


def test_ask_wiki_notes_epi_cli_is_same_source_fallback():
    ask = _read(PUBLIC_SKILL / "workflows" / "ask-wiki.md")

    assert "wiki-ask" in ask
    assert ("fallback" in ask.lower()) or ("程序化" in ask) or ("同源" in ask)
