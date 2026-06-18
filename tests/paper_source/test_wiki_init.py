import json
import subprocess

from paper_source.artifacts import (
    existing_paper_source_root,
    existing_raw_paper_root,
    existing_run_dir,
    existing_runs_root,
    existing_staging_paper_root,
)
from paper_source.paper_source_repository import cleanup_paper_source_repository, load_retention_policy, migrate_legacy_paper_source_roots
from paper_source.wiki_init import initialize_paper_wiki


EXPECTED_RESEARCH_WIKI_DIRS = [
    "references",
    "concepts",
    "derivations",
    "experiments",
    "synthesis",
    "reports",
    "opportunities",
]


def test_initialize_paper_wiki_creates_required_layout(tmp_path):
    vault = tmp_path / "paper-research-wiki"

    created = initialize_paper_wiki(vault)

    expected_dirs = [
        "_paper_source/raw",
        "_paper_source/staging/papers",
        "_paper_source/staging/wiki-batches/pending",
        "_paper_source/meta",
        "_paper_source/meta/formal-page-snapshots",
        "_paper_source/policies",
        "_meta",
        *EXPECTED_RESEARCH_WIKI_DIRS,
        ".obsidian",
    ]
    for relative_path in expected_dirs:
        assert (vault / relative_path).is_dir()

    on_demand_dirs = [
        "_paper_source/runs",
        "_paper_source/cache",
        "_paper_source/tmp",
        "_paper_source/tmp-manual-pdfs",
        "_paper_source/quarantine",
        "_paper_source/evolution",
        "_paper_source/meta/raw-cleanup",
    ]
    for relative_path in on_demand_dirs:
        assert not (vault / relative_path).exists()

    manifest = json.loads((vault / ".manifest.json").read_text(encoding="utf-8"))
    assert manifest["vault_type"] == "academic-paper-research"
    assert manifest["source_first_wiki_ingest"] is True
    assert manifest["git_repository_required"] is True
    assert manifest["git_auto_init"] is True
    assert manifest["git_initial_commit"] is False
    assert "mineru/<slug>.md" in manifest["must_read_source_artifacts"]
    assert "mineru/images/*" in manifest["must_read_source_artifacts"]
    assert "wiki-ingest-brief.json" in manifest["handoff_artifacts"]
    assert manifest["formula_rendering"]["inline"] == "$...$"
    assert manifest["formula_rendering"]["block"] == "$$...$$"
    assert manifest["formula_rendering"]["forbidden_fenced_languages"] == ["math", "tex", "latex"]
    assert manifest["paper_source_internal_root"] == "_paper_source"
    assert manifest["operational_dirs"] == ["_paper_source"]
    assert manifest["wiki_dirs"][:7] == EXPECTED_RESEARCH_WIKI_DIRS
    assert (vault / "AGENTS.md").is_file()
    assert (vault / "_paper_source" / "README.md").is_file()
    assert (vault / "_paper_source" / "manifest.json").is_file()
    assert (vault / "_paper_source" / "policies" / "retention.json").is_file()
    retention = json.loads((vault / "_paper_source" / "policies" / "retention.json").read_text(encoding="utf-8"))
    assert retention["max_total_files"] == 3000
    assert retention["max_total_bytes"] == 1024 * 1024 * 1024
    assert retention["lifecycle"]["enforce_even_when_under_budget"] is True
    assert retention["lifecycle"]["meta_manifests"]["run-lifecycle"]["keep_latest"] == 20
    assert retention["lifecycle"]["meta_manifests"]["raw-cleanup"]["keep_latest"] == 30
    assert retention["lifecycle"]["formal_page_snapshots"]["keep_latest"] == 3
    assert retention["lifecycle"]["temporary_files"]["tmp-manual-pdfs"]["keep_latest"] == 5
    assert "meta/paper-source-config.yaml" in retention["protected"]
    assert "meta/paper-source-config-state.json" in retention["protected"]
    assert "meta/epi-config.yaml" not in retention["protected"]
    assert "meta/epi-config-state.json" not in retention["protected"]
    assert (vault / "_meta" / "agent-operating-contract.md").is_file()
    assert (vault / "_meta" / "schema.md").is_file()
    assert (vault / "_meta" / "taxonomy.md").is_file()
    assert (vault / "_meta" / "directory-structure.md").is_file()
    assert "Source-first paper ingest" in (vault / "AGENTS.md").read_text(encoding="utf-8")
    assert "_paper_source/raw" in (vault / "_paper_source" / "README.md").read_text(encoding="utf-8")
    agents = (vault / "AGENTS.md").read_text(encoding="utf-8")
    operating_contract = (vault / "_meta" / "agent-operating-contract.md").read_text(encoding="utf-8")
    schema = (vault / "_meta" / "schema.md").read_text(encoding="utf-8")
    assert "Obsidian math rendering" in agents
    assert "```math" in agents
    assert "legacy `_epi/**`" in agents
    assert "qmd ls paper-research-wiki/_epi" not in agents
    assert "mineru/paper.tex" in operating_contract
    assert "block `$$...$$`" in operating_contract
    assert "fenced `math`, `tex`, or `latex`" in operating_contract
    assert "legacy `_epi/**`" in operating_contract
    assert "figures/tables/images" in schema
    assert "Formula Rendering Contract" in schema
    assert "Do not use fenced code blocks labelled `math`, `tex`, or `latex`" in schema
    taxonomy = (vault / "_meta" / "taxonomy.md").read_text(encoding="utf-8")
    directory_structure = (vault / "_meta" / "directory-structure.md").read_text(encoding="utf-8")
    for wiki_dir in EXPECTED_RESEARCH_WIKI_DIRS:
        assert f"`{wiki_dir}/`" in taxonomy
        assert f"`{wiki_dir}/`" in directory_structure
    assert "formula derivation" in taxonomy
    assert "implementability" in taxonomy
    assert "research gap" in taxonomy
    assert "on-demand workflow directories" in directory_structure
    assert "`_paper_source/quarantine/`" in directory_structure
    assert "`_paper_source/evolution/`" in directory_structure
    graph_visibility = (vault / "_meta" / "graph-visibility.md").read_text(encoding="utf-8")
    assert "_paper_source/" in graph_visibility
    assert "legacy `_epi/` when present" in graph_visibility
    assert "global `search` empty" in graph_visibility
    graph = json.loads((vault / ".obsidian" / "graph.json").read_text(encoding="utf-8"))
    assert graph["search"] == ""
    assert graph["collapse-filter"] is True
    app = json.loads((vault / ".obsidian" / "app.json").read_text(encoding="utf-8"))
    for ignored in ["_epi/", "_paper_source/", "_meta/", ".claude/", "AGENTS.md", "hot.md", "log.md"]:
        assert ignored in app["userIgnoreFilters"]
    assert (vault / ".git").is_dir()
    assert ".git" in created
    assert (
        subprocess.run(
            ["git", "-C", str(vault), "rev-parse", "--is-inside-work-tree"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        == "true"
    )
    assert (
        subprocess.run(
            ["git", "-C", str(vault), "rev-parse", "--verify", "HEAD"],
            capture_output=True,
            text=True,
        ).returncode
        != 0
    )
    assert "index.md" in created
    assert "_paper_source/README.md" in created
    assert not (vault / "_raw").exists()
    assert not (vault / "_staging").exists()
    assert not (vault / "_runs").exists()
    assert not (vault / "entities").exists()
    assert not (vault / "skills").exists()
    assert not (vault / "projects").exists()
    assert not (vault / "journal").exists()


def test_initialize_paper_wiki_repairs_legacy_contract_files_without_losing_manifest_papers(tmp_path):
    vault = tmp_path / "paper-research-wiki"
    (vault / "_meta").mkdir(parents=True)
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "AGENTS.md").write_text("- `_staging/papers/<slug>/wiki-ingest-brief.json`\n", encoding="utf-8")
    (vault / "_meta" / "directory-structure.md").write_text("- `_raw/papers/<slug>/`\n", encoding="utf-8")
    (vault / "_meta" / "graph-visibility.md").write_text("- `_raw/papers/<slug>/mineru/title.md`\n", encoding="utf-8")
    (vault / ".manifest.json").write_text(
        json.dumps(
            {
                "vault_type": "engineering-paper-research",
                "operational_dirs": ["_raw", "_staging", "_runs"],
                "papers": [{"paper_slug": "kept-paper", "status": "wiki_ingest_recorded"}],
            }
        ),
        encoding="utf-8",
    )
    (vault / ".obsidian" / "graph.json").write_text(
        json.dumps(
            {
                "search": "path:/^_raw\\/papers\\//",
                "showTags": True,
                "showAttachments": True,
            }
        ),
        encoding="utf-8",
    )

    created = initialize_paper_wiki(vault)

    assert "AGENTS.md" in created
    assert "_meta/directory-structure.md" in created
    assert "_meta/graph-visibility.md" in created
    assert ".manifest.json" in created
    assert ".obsidian/graph.json" in created
    assert ".obsidian/app.json" in created
    assert "_paper_source/staging/papers/<slug>/wiki-ingest-brief.json" in (vault / "AGENTS.md").read_text(encoding="utf-8")
    assert "_raw" not in (vault / "_meta" / "directory-structure.md").read_text(encoding="utf-8")
    assert "_paper_source/" in (vault / "_meta" / "graph-visibility.md").read_text(encoding="utf-8")
    manifest = json.loads((vault / ".manifest.json").read_text(encoding="utf-8"))
    assert manifest["vault_type"] == "engineering-paper-research"
    assert manifest["operational_dirs"] == ["_paper_source"]
    assert manifest["paper_source_internal_root"] == "_paper_source"
    assert manifest["wiki_dirs"][:7] == EXPECTED_RESEARCH_WIKI_DIRS
    assert manifest["papers"] == [{"paper_slug": "kept-paper", "status": "wiki_ingest_recorded"}]
    graph = json.loads((vault / ".obsidian" / "graph.json").read_text(encoding="utf-8"))
    assert graph["search"] == ""
    assert graph["showTags"] is True
    assert graph["showAttachments"] is True


def test_graph_visibility_filter_clears_legacy_formal_path_search(tmp_path):
    vault = tmp_path / "paper-research-wiki"
    (vault / ".obsidian").mkdir(parents=True)
    overescaped = "path:/^index\\.md$/ OR path:/^references\\\\\\\\//"
    (vault / ".obsidian" / "graph.json").write_text(
        json.dumps({"search": overescaped, "showTags": True}),
        encoding="utf-8",
    )

    created = initialize_paper_wiki(vault)

    graph = json.loads((vault / ".obsidian" / "graph.json").read_text(encoding="utf-8"))
    assert ".obsidian/graph.json" in created
    assert graph["search"] == ""
    assert graph["showTags"] is True


def test_graph_visibility_filter_repairs_collapse_filter_when_search_is_current(tmp_path):
    from paper_source.graph_visibility import graph_search_filter

    vault = tmp_path / "paper-research-wiki"
    (vault / ".obsidian").mkdir(parents=True)
    current_search = graph_search_filter(EXPECTED_RESEARCH_WIKI_DIRS)
    (vault / ".obsidian" / "graph.json").write_text(
        json.dumps({"search": current_search, "collapse-filter": False, "showTags": True}),
        encoding="utf-8",
    )

    created = initialize_paper_wiki(vault)

    graph = json.loads((vault / ".obsidian" / "graph.json").read_text(encoding="utf-8"))
    assert ".obsidian/graph.json" in created
    assert graph["search"] == ""
    assert graph["collapse-filter"] is True
    assert graph["showTags"] is True


def test_graph_visibility_app_json_merges_required_ignore_filters(tmp_path):
    vault = tmp_path / "paper-research-wiki"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / ".obsidian" / "app.json").write_text(
        json.dumps({"userIgnoreFilters": ["private-notes/"], "spellcheck": False}),
        encoding="utf-8",
    )

    created = initialize_paper_wiki(vault)

    app = json.loads((vault / ".obsidian" / "app.json").read_text(encoding="utf-8"))
    assert ".obsidian/app.json" in created
    assert app["spellcheck"] is False
    assert app["userIgnoreFilters"][0] == "private-notes/"
    for ignored in ["_epi/", "_paper_source/", "_meta/", ".claude/", "AGENTS.md", "hot.md", "log.md"]:
        assert ignored in app["userIgnoreFilters"]


def test_initialize_paper_wiki_preserves_existing_git_repo(tmp_path):
    vault = tmp_path / "paper-research-wiki"
    vault.mkdir(parents=True)
    subprocess.run(["git", "-C", str(vault), "init"], check=True, capture_output=True, text=True)

    created = initialize_paper_wiki(vault)

    assert ".git" not in created
    assert (vault / ".git").is_dir()


def test_migrate_legacy_paper_source_roots_moves_operational_dirs_under_single_paper_source_root(tmp_path):
    vault = tmp_path / "paper-research-wiki"
    (vault / "_raw" / "papers" / "paper-a").mkdir(parents=True)
    (vault / "_raw" / "papers" / "paper-a" / "metadata.json").write_text("{}", encoding="utf-8")
    (vault / "_staging" / "papers" / "paper-a").mkdir(parents=True)
    (vault / "_staging" / "papers" / "paper-a" / "wiki-ingest-brief.json").write_text("{}", encoding="utf-8")
    (vault / "_runs" / "run-1").mkdir(parents=True)
    (vault / "_runs" / "run-1" / "run-state.json").write_text("{}", encoding="utf-8")
    (vault / "_meta").mkdir(parents=True)
    (vault / "_meta" / "paper-source-config.yaml").write_text("profile: test\n", encoding="utf-8")
    (vault / "_meta" / "schema.md").write_text("# Schema\n", encoding="utf-8")

    preview = migrate_legacy_paper_source_roots(vault, dry_run=True)
    result = migrate_legacy_paper_source_roots(vault)

    assert preview["status"] == "preview"
    assert result["status"] == "migrated"
    assert (vault / "_paper_source" / "raw" / "paper-a" / "metadata.json").is_file()
    assert (vault / "_paper_source" / "staging" / "papers" / "paper-a" / "wiki-ingest-brief.json").is_file()
    assert (vault / "_paper_source" / "runs" / "run-1" / "run-state.json").is_file()
    assert (vault / "_paper_source" / "meta" / "paper-source-config.yaml").is_file()
    assert (vault / "_meta" / "schema.md").is_file()
    assert not (vault / "_raw").exists()
    assert not (vault / "_staging").exists()
    assert not (vault / "_runs").exists()
    assert (vault / "_paper_source" / "manifest.json").is_file()
    assert result["manifest_path"].endswith("legacy-roots.json")


def test_migrate_legacy_nested_paper_source_raw_papers_to_direct_raw_slug_dirs(tmp_path):
    vault = tmp_path / "paper-research-wiki"
    legacy_nested_paper = vault / "_paper_source" / "raw" / "papers" / "paper-a"
    legacy_nested_paper.mkdir(parents=True)
    (legacy_nested_paper / "metadata.json").write_text(json.dumps({"slug": "paper-a"}), encoding="utf-8")

    result = migrate_legacy_paper_source_roots(vault)

    assert result["status"] == "migrated"
    assert not (vault / "_paper_source" / "raw" / "papers" / "paper-a").exists()
    assert (vault / "_paper_source" / "raw" / "paper-a" / "metadata.json").is_file()


def test_migrate_legacy_paper_source_roots_preview_does_not_write_repository_files(tmp_path):
    vault = tmp_path / "paper-research-wiki"
    (vault / "_paper_source" / "raw" / "papers" / "paper-a").mkdir(parents=True)
    (vault / "_paper_source" / "raw" / "papers" / "paper-a" / "metadata.json").write_text("{}", encoding="utf-8")

    result = migrate_legacy_paper_source_roots(vault, dry_run=True)

    assert result["status"] == "preview"
    assert result["actions"]
    assert (vault / "_paper_source" / "raw" / "papers" / "paper-a" / "metadata.json").is_file()
    assert not (vault / "_paper_source" / "raw" / "paper-a").exists()
    assert not (vault / "_paper_source" / "manifest.json").exists()
    assert not (vault / "_paper_source" / "policies" / "retention.json").exists()


def test_repository_cleanup_preview_does_not_write_manifest(tmp_path):
    vault = tmp_path / "paper-research-wiki"
    run_dir = vault / "_paper_source" / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    (run_dir / "run-state.json").write_text(json.dumps({"status": "success"}), encoding="utf-8")

    result = cleanup_paper_source_repository(vault, dry_run=True)

    assert result["status"] == "preview"
    assert not (vault / "_paper_source" / "manifest.json").exists()
    assert not (vault / "_paper_source" / "policies" / "retention.json").exists()


def test_load_retention_policy_upgrades_legacy_default_policy_without_preview_write(tmp_path):
    vault = tmp_path / "paper-research-wiki"
    policy_path = vault / "_paper_source" / "policies" / "retention.json"
    policy_path.parent.mkdir(parents=True)
    legacy = {
        "schema_version": "paper-source-retention-policy-v1",
        "auto_cleanup_enabled": True,
        "max_total_files": 12000,
        "max_total_bytes": 5 * 1024 * 1024 * 1024,
        "runs": {"keep_latest": 15, "keep_per_workflow": 2},
        "staging": {"keep_pending_wiki_batches": 8},
        "protected": ["raw/papers", "meta/paper-source-config.yaml", "policies/retention.json"],
    }
    policy_path.write_text(json.dumps(legacy), encoding="utf-8")

    preview_policy = load_retention_policy(vault, ensure=False)

    assert preview_policy["max_total_files"] == 3000
    assert preview_policy["max_total_bytes"] == 1024 * 1024 * 1024
    assert preview_policy["lifecycle"]["enforce_even_when_under_budget"] is True
    assert json.loads(policy_path.read_text(encoding="utf-8"))["max_total_files"] == 12000

    applied_policy = load_retention_policy(vault, ensure=True)

    stored = json.loads(policy_path.read_text(encoding="utf-8"))
    assert applied_policy["max_total_files"] == 3000
    assert stored["max_total_files"] == 3000
    assert stored["protected"][0] == "raw"
    assert "meta/paper-source-config.yaml" in stored["protected"]
    assert "meta/paper-source-config-state.json" in stored["protected"]
    assert "meta/epi-config.yaml" not in stored["protected"]
    assert "meta/epi-config-state.json" not in stored["protected"]
    assert "lifecycle" in stored


def test_current_path_helpers_do_not_fallback_to_retired_roots(tmp_path):
    vault = tmp_path / "paper-research-wiki"
    (vault / "_epi" / "raw" / "paper-a").mkdir(parents=True)
    (vault / "_epi" / "staging" / "papers" / "paper-a").mkdir(parents=True)
    (vault / "_epi" / "runs" / "run-a").mkdir(parents=True)
    (vault / "_raw" / "papers" / "paper-a").mkdir(parents=True)
    (vault / "_staging" / "papers" / "paper-a").mkdir(parents=True)
    (vault / "_runs" / "run-a").mkdir(parents=True)

    assert existing_paper_source_root(vault) == vault.resolve() / "_paper_source"
    assert existing_raw_paper_root(vault, "paper-a") == (
        vault.resolve() / "_paper_source" / "raw" / "paper-a"
    )
    assert existing_staging_paper_root(vault, "paper-a") == (
        vault.resolve() / "_paper_source" / "staging" / "papers" / "paper-a"
    )
    assert existing_runs_root(vault) == vault.resolve() / "_paper_source" / "runs"
    assert existing_run_dir(vault, "run-a") == vault.resolve() / "_paper_source" / "runs" / "run-a"


def test_load_retention_policy_ignores_retired_epi_policy(tmp_path):
    vault = tmp_path / "paper-research-wiki"
    legacy_policy = vault / "_epi" / "policies" / "retention.json"
    legacy_policy.parent.mkdir(parents=True)
    legacy_policy.write_text(
        json.dumps(
            {
                "schema_version": "paper-source-retention-policy-v1",
                "auto_cleanup_enabled": False,
                "max_total_files": 42,
                "max_total_bytes": 43,
                "protected": ["legacy-only"],
            }
        ),
        encoding="utf-8",
    )

    preview_policy = load_retention_policy(vault, ensure=False)

    assert preview_policy["auto_cleanup_enabled"] is True
    assert preview_policy["max_total_files"] == 3000
    assert preview_policy["max_total_bytes"] == 1024 * 1024 * 1024
    assert "legacy-only" not in preview_policy["protected"]


def test_repository_cleanup_prunes_lifecycle_artifacts_even_when_under_budget(tmp_path):
    vault = tmp_path / "paper-research-wiki"
    policy_path = vault / "_paper_source" / "policies" / "retention.json"
    policy_path.parent.mkdir(parents=True)
    policy_path.write_text(
        json.dumps(
            {
                "auto_cleanup_enabled": True,
                "max_total_files": 9999,
                "max_total_bytes": 999999999,
                "runs": {"keep_latest": 2},
                "lifecycle": {
                    "enforce_even_when_under_budget": True,
                    "meta_manifests": {
                        "run-lifecycle": {"keep_latest": 2},
                        "raw-cleanup": {"keep_latest": 1},
                    },
                    "formal_page_snapshots": {"keep_latest": 1},
                    "temporary_files": {"tmp-manual-pdfs": {"keep_latest": 1}},
                },
            }
        ),
        encoding="utf-8",
    )
    for index in range(4):
        run_dir = vault / "_paper_source" / "runs" / f"run-{index}"
        run_dir.mkdir(parents=True)
        (run_dir / "run-state.json").write_text(json.dumps({"status": "success"}), encoding="utf-8")
        lifecycle = vault / "_paper_source" / "meta" / "run-lifecycle" / f"{index}-run-lifecycle.json"
        lifecycle.parent.mkdir(parents=True, exist_ok=True)
        lifecycle.write_text(json.dumps({"index": index}), encoding="utf-8")
        raw_cleanup = vault / "_paper_source" / "meta" / "raw-cleanup" / f"{index}-cleanup.json"
        raw_cleanup.parent.mkdir(parents=True, exist_ok=True)
        raw_cleanup.write_text(json.dumps({"index": index}), encoding="utf-8")
        snapshot = vault / "_paper_source" / "meta" / "formal-page-snapshots" / f"snapshot-{index}"
        snapshot.mkdir(parents=True)
        (snapshot / "snapshot-manifest.json").write_text(json.dumps({"index": index}), encoding="utf-8")
        manual_pdf = vault / "_paper_source" / "tmp-manual-pdfs" / f"paper-{index}.pdf"
        manual_pdf.parent.mkdir(parents=True, exist_ok=True)
        manual_pdf.write_bytes(b"%PDF-1.4\n")

    result = cleanup_paper_source_repository(vault)

    assert result["over_budget"] is False
    assert result["deleted_count"] == 13
    assert sorted(path.name for path in (vault / "_paper_source" / "runs").iterdir() if path.is_dir()) == ["run-2", "run-3"]
    assert sorted(path.name for path in (vault / "_paper_source" / "meta" / "run-lifecycle").iterdir()) == [
        "2-run-lifecycle.json",
        "3-run-lifecycle.json",
    ]
    assert sorted(path.name for path in (vault / "_paper_source" / "meta" / "raw-cleanup").iterdir()) == ["3-cleanup.json"]
    assert sorted(path.name for path in (vault / "_paper_source" / "meta" / "formal-page-snapshots").iterdir()) == [
        "snapshot-3"
    ]
    assert sorted(path.name for path in (vault / "_paper_source" / "tmp-manual-pdfs").iterdir()) == ["paper-3.pdf"]


def test_repository_cleanup_removes_empty_on_demand_shell_dirs(tmp_path):
    vault = tmp_path / "paper-research-wiki"
    initialize_paper_wiki(vault)

    empty_shells = [
        vault / "_paper_source" / "cache" / "easyscholar",
        vault / "_paper_source" / "quarantine" / "papers",
        vault / "_paper_source" / "evolution" / "proposals",
        vault / "_paper_source" / "evolution" / "pending",
    ]
    for path in empty_shells:
        path.mkdir(parents=True, exist_ok=True)

    non_empty_tmp = vault / "_paper_source" / "tmp" / "downloads"
    non_empty_tmp.mkdir(parents=True)
    (non_empty_tmp / "keep.pdf").write_text("keep", encoding="utf-8")

    preview = cleanup_paper_source_repository(vault, dry_run=True)
    assert any(action["action"] == "remove-empty-on-demand-dir" for action in preview["actions"])
    assert (vault / "_paper_source" / "quarantine").exists()
    assert non_empty_tmp.exists()

    result = cleanup_paper_source_repository(vault)

    assert result["status"] == "cleaned"
    assert not (vault / "_paper_source" / "cache").exists()
    assert not (vault / "_paper_source" / "quarantine").exists()
    assert not (vault / "_paper_source" / "evolution").exists()
    assert non_empty_tmp.exists()
