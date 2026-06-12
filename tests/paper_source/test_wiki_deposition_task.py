import json

from paper_source.stage_wiki import stage_paper


EXPECTED_PAGE_FAMILIES = [
    "references",
    "concepts",
    "derivations",
    "experiments",
    "synthesis",
    "reports",
    "opportunities",
]

EXPECTED_CORE_SKILLS = [
    "paper-research-wiki",
    "paper-source-paper-deposition",
]

EXPECTED_FRONTMATTER_FIELDS = [
    "title",
    "category",
    "page_family",
    "tags",
    "aliases",
    "sources",
    "summary",
    "provenance",
    "base_confidence",
    "lifecycle",
    "lifecycle_changed",
    "tier",
    "created",
    "updated",
]


def _seed_source_bundle(vault, slug="fixture-paper"):
    paper_root = vault / "_paper_source" / "raw" / slug
    mineru_root = paper_root / "mineru"
    image_root = mineru_root / "images"
    image_root.mkdir(parents=True, exist_ok=True)
    (paper_root / "paper.pdf").write_bytes(b"%PDF-1.4\nfixture\n")
    (paper_root / "metadata.json").write_text(
        json.dumps(
            {
                "slug": slug,
                "title": "Fixture Paper",
                "doi": "10.1000/fixture",
                "venue": "IROS",
                "year": 2026,
            }
        ),
        encoding="utf-8",
    )
    (mineru_root / f"{slug}.md").write_text("# Paper\n\nMethod and experiments.\n", encoding="utf-8")
    (mineru_root / "paper.tex").write_text("\\section{Method}\n", encoding="utf-8")
    (image_root / "figure-1.png").write_bytes(b"image")
    (mineru_root / "mineru-manifest.json").write_text(
        json.dumps({"outputs": [{"file_name": "paper.pdf", "state": "done"}]}),
        encoding="utf-8",
    )
    return paper_root


def _posix(value):
    return str(value).replace("\\", "/")


def test_stage_paper_writes_brief_canonical_handoff_by_default(tmp_path):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    paper_root = _seed_source_bundle(vault, slug)

    staging_root = stage_paper(vault, slug, paper_root)

    brief_path = staging_root / "wiki-ingest-brief.json"
    task_path = staging_root / "wiki_deposition_task.json"
    plan_path = staging_root / "promotion-plan.json"

    assert brief_path.is_file()
    assert not task_path.exists()

    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    assert brief["schema_version"] == "paper-source-wiki-ingest-brief-v1"
    assert brief["handoff_type"] == "agent-mediated-wiki-ingest"
    assert brief["ingest_policy"]["required_wiki_skills"] == EXPECTED_CORE_SKILLS
    assert brief["wiki_skill_handoff"]["required_skills"] == EXPECTED_CORE_SKILLS
    assert "wiki_deposition_task" not in brief
    legacy = brief["legacy_wiki_deposition_task"]
    assert legacy["schema_version"] == "paper-source-wiki-deposition-task-v1"
    assert legacy["status"] == "not-emitted"
    assert legacy["task_path"] is None
    assert legacy["canonical_handoff"] == "wiki-ingest-brief.json"
    assert legacy["reason"] == "wiki-ingest-brief.json is the canonical Paper Source-to-Paper Wiki handoff"
    assert "epi-wiki-deposition" in legacy["compatibility_aliases"]
    assert brief["formal_page_families"] == EXPECTED_PAGE_FAMILIES
    assert brief["formal_frontmatter_schema"]["required_fields"] == EXPECTED_FRONTMATTER_FIELDS
    assert plan["wiki_ingest_brief_path"] == str(brief_path)
    assert "wiki_deposition_task_path" not in plan
    assert "legacy_wiki_deposition_task_path" not in plan
    assert str(task_path) not in plan["agent_handoff_paths"]


def test_stage_paper_can_emit_legacy_wiki_deposition_task_when_requested(tmp_path):
    from paper_source.wiki_handoff_contracts import agent_context_policy

    vault = tmp_path / "vault"
    slug = "fixture-paper"
    paper_root = _seed_source_bundle(vault, slug)

    staging_root = stage_paper(vault, slug, paper_root, emit_legacy_deposition_task=True)

    task_path = staging_root / "wiki_deposition_task.json"
    assert task_path.is_file()
    task = json.loads(task_path.read_text(encoding="utf-8"))

    assert task["schema_version"] == "paper-source-wiki-deposition-task-v1"
    assert task["task_type"] == "wiki_deposition"
    assert task["vault_schema"] == "paper-source-paper-research"
    assert task["page_families"] == EXPECTED_PAGE_FAMILIES
    assert task["required_skills"] == EXPECTED_CORE_SKILLS
    assert task["required_skills"][:2] == ["paper-research-wiki", "paper-source-paper-deposition"]
    assert "epi-wiki-deposition" in task["compatibility_aliases"]
    assert task["handoff_boundary"]["paper_source_core_role"] == "source-bundle-and-audit-only"
    assert "epi_core_role" not in task["handoff_boundary"]
    assert task["handoff_boundary"]["formal_writer_role"] == "obsidian-wiki-skill-layer"
    assert task["handoff_boundary"]["canonical_internal_roots"] == ["_paper_source/"]
    assert task["handoff_boundary"]["legacy_internal_roots"] == ["_epi/"]
    assert "internal_roots" not in task["handoff_boundary"]
    assert task["agent_context_policy"] == agent_context_policy()
    assert task["agent_context_policy"]["delegation_model"] == "clean-worker-final-artifacts"
    assert task["agent_context_policy"]["main_agent_reads"] == [
        "final worker output",
        "changed file list",
        "verification result",
    ]
    assert "large intermediate transcripts" in task["agent_context_policy"]["main_agent_avoids"]
    rule_source_model = task["wiki_rule_source_model"]
    rule_sources = [item["source"] for item in rule_source_model["resolution_order"]]
    assert any("paper-research-wiki" in source for source in rule_sources)
    paper_wiki_index = next(index for index, source in enumerate(rule_sources) if "paper-research-wiki" in source)
    local_index = rule_sources.index("local llm-wiki / wiki-ingest / obsidian-markdown skills")
    assert paper_wiki_index < local_index

    paper = task["papers"][0]
    assert paper["slug"] == slug
    assert _posix(paper["metadata"]).endswith("_paper_source/raw/fixture-paper/metadata.json")
    assert _posix(paper["paper_md"]).endswith("_paper_source/raw/fixture-paper/mineru/fixture-paper.md")
    assert _posix(paper["paper_tex"]).endswith("_paper_source/raw/fixture-paper/mineru/paper.tex")
    assert _posix(paper["images"]).endswith("_paper_source/raw/fixture-paper/mineru/images")
    assert _posix(paper["formula_index"]).endswith("_paper_source/raw/fixture-paper/formula-index.json")
    assert _posix(paper["figure_index"]).endswith("_paper_source/raw/fixture-paper/figure-index.json")
    assert _posix(paper["brief"]).endswith("_paper_source/staging/papers/fixture-paper/wiki-ingest-brief.json")

    quality_gates = task["quality_gates"]
    for gate in [
        "frontmatter_required",
        "compiled_knowledge_required",
        "formula_derivation_required",
        "human_stage_review_required",
        "lint_required",
        "stage_commit_required",
    ]:
        assert quality_gates[gate] is True
    assert "math" in quality_gates["forbidden_fenced_formula_languages"]
    assert "_paper_source" in quality_gates["internal_roots_forbidden_in_formal_graph"]

    frontmatter = task["formal_frontmatter_schema"]
    assert frontmatter["required_fields"] == EXPECTED_FRONTMATTER_FIELDS
    assert frontmatter["provenance_required_fields"] == ["extracted", "inferred", "ambiguous"]
    assert frontmatter["category_must_match_page_family"] is True
    assert frontmatter["initial_lifecycle_values"] == ["draft"]
    assert frontmatter["allowed_lifecycle_values"] == ["draft"]

    brief = json.loads((staging_root / "wiki-ingest-brief.json").read_text(encoding="utf-8"))
    plan = json.loads((staging_root / "promotion-plan.json").read_text(encoding="utf-8"))
    assert "wiki_deposition_task" not in brief
    legacy = brief["legacy_wiki_deposition_task"]
    assert legacy["status"] == "emitted"
    assert legacy["task_path"] == str(task_path)
    assert legacy["canonical_handoff"] == "wiki-ingest-brief.json"
    assert brief["agent_context_policy"] == task["agent_context_policy"]
    assert brief["wiki_skill_handoff"]["agent_context_policy"] == task["agent_context_policy"]
    assert brief["wiki_skill_handoff"]["required_skills"] == EXPECTED_CORE_SKILLS
    minimum_role = brief["wiki_skill_handoff"]["minimum_role"]
    for skill in EXPECTED_CORE_SKILLS:
        assert skill in minimum_role
    assert "load paper-research-wiki first" in minimum_role
    assert "paper-source-paper-deposition" in minimum_role
    assert "compatibility adapter" in minimum_role
    assert "load paper-source-paper-deposition, llm-wiki" not in minimum_role
    assert brief["formal_frontmatter_schema"] == frontmatter
    assert plan["legacy_wiki_deposition_task_path"] == str(task_path)
    assert str(task_path) in plan["agent_handoff_paths"]


def test_paper_source_paper_deposition_skill_documents_adapter_boundary():
    skill_path = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "plugins" / "paper-source"
        / "skills"
        / "paper-source-paper-deposition"
        / "SKILL.md"
    )

    text = skill_path.read_text(encoding="utf-8")

    assert "name: paper-source-paper-deposition" in text
    assert "wiki-ingest-brief.json" in text
    assert "legacy `wiki_deposition_task.json`" in text
    assert "$paper-research-wiki" in text
    assert "epi-wiki-deposition" in text
    assert "llm-wiki" not in text
    assert "wiki-stage-commit" not in text
    assert "Required frontmatter fields" not in text
    assert "must not enter the formal graph" in text
