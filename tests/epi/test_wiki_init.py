import json
import subprocess

from epi.epi_repository import migrate_legacy_epi_roots
from epi.wiki_init import initialize_paper_wiki


def test_initialize_paper_wiki_creates_required_layout(tmp_path):
    vault = tmp_path / "paper-research-wiki"

    created = initialize_paper_wiki(vault)

    expected_dirs = [
        "_epi/raw/papers",
        "_epi/staging/papers",
        "_epi/staging/wiki-batches/pending",
        "_epi/quarantine/papers",
        "_epi/runs",
        "_epi/evolution/proposals",
        "_epi/evolution/pending",
        "_epi/evolution/active",
        "_epi/evolution/archive",
        "_epi/evolution/rejected",
        "_epi/meta",
        "_epi/policies",
        "_meta",
        "references",
        "concepts",
        "synthesis",
        "entities",
        "skills",
        "projects",
        "journal",
        ".obsidian",
    ]
    for relative_path in expected_dirs:
        assert (vault / relative_path).is_dir()

    manifest = json.loads((vault / ".manifest.json").read_text(encoding="utf-8"))
    assert manifest["vault_type"] == "academic-paper-research"
    assert manifest["source_first_wiki_ingest"] is True
    assert manifest["git_repository_required"] is True
    assert manifest["git_auto_init"] is True
    assert manifest["git_initial_commit"] is False
    assert "mineru/<slug>.md" in manifest["must_read_source_artifacts"]
    assert "mineru/images/*" in manifest["must_read_source_artifacts"]
    assert "wiki-ingest-brief.json" in manifest["handoff_artifacts"]
    assert manifest["epi_internal_root"] == "_epi"
    assert manifest["operational_dirs"] == ["_epi"]
    assert (vault / "AGENTS.md").is_file()
    assert (vault / "_epi" / "README.md").is_file()
    assert (vault / "_epi" / "manifest.json").is_file()
    assert (vault / "_epi" / "policies" / "retention.json").is_file()
    assert (vault / "_meta" / "agent-operating-contract.md").is_file()
    assert (vault / "_meta" / "schema.md").is_file()
    assert (vault / "_meta" / "taxonomy.md").is_file()
    assert (vault / "_meta" / "directory-structure.md").is_file()
    assert "Source-first paper ingest" in (vault / "AGENTS.md").read_text(encoding="utf-8")
    assert "_epi/raw/papers" in (vault / "_epi" / "README.md").read_text(encoding="utf-8")
    assert "mineru/paper.tex" in (vault / "_meta" / "agent-operating-contract.md").read_text(encoding="utf-8")
    assert "figures/tables/images" in (vault / "_meta" / "schema.md").read_text(encoding="utf-8")
    assert "_epi/" in (vault / "_meta" / "graph-visibility.md").read_text(encoding="utf-8")
    graph = json.loads((vault / ".obsidian" / "graph.json").read_text(encoding="utf-8"))
    assert "_epi" not in graph["search"]
    assert "_raw" not in graph["search"]
    assert "path:/^references\\//" in graph["search"]
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
    assert "_epi/README.md" in created
    assert not (vault / "_raw").exists()
    assert not (vault / "_staging").exists()
    assert not (vault / "_runs").exists()


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
    assert "_epi/staging/papers/<slug>/wiki-ingest-brief.json" in (vault / "AGENTS.md").read_text(encoding="utf-8")
    assert "_raw" not in (vault / "_meta" / "directory-structure.md").read_text(encoding="utf-8")
    assert "_epi/" in (vault / "_meta" / "graph-visibility.md").read_text(encoding="utf-8")
    manifest = json.loads((vault / ".manifest.json").read_text(encoding="utf-8"))
    assert manifest["vault_type"] == "engineering-paper-research"
    assert manifest["operational_dirs"] == ["_epi"]
    assert manifest["epi_internal_root"] == "_epi"
    assert manifest["papers"] == [{"paper_slug": "kept-paper", "status": "wiki_ingest_recorded"}]
    graph = json.loads((vault / ".obsidian" / "graph.json").read_text(encoding="utf-8"))
    assert "_raw" not in graph["search"]
    assert "_epi" not in graph["search"]
    assert graph["showTags"] is True
    assert graph["showAttachments"] is True


def test_initialize_paper_wiki_preserves_existing_git_repo(tmp_path):
    vault = tmp_path / "paper-research-wiki"
    vault.mkdir(parents=True)
    subprocess.run(["git", "-C", str(vault), "init"], check=True, capture_output=True, text=True)

    created = initialize_paper_wiki(vault)

    assert ".git" not in created
    assert (vault / ".git").is_dir()


def test_migrate_legacy_epi_roots_moves_operational_dirs_under_single_epi_root(tmp_path):
    vault = tmp_path / "paper-research-wiki"
    (vault / "_raw" / "papers" / "paper-a").mkdir(parents=True)
    (vault / "_raw" / "papers" / "paper-a" / "metadata.json").write_text("{}", encoding="utf-8")
    (vault / "_staging" / "papers" / "paper-a").mkdir(parents=True)
    (vault / "_staging" / "papers" / "paper-a" / "wiki-ingest-brief.json").write_text("{}", encoding="utf-8")
    (vault / "_runs" / "run-1").mkdir(parents=True)
    (vault / "_runs" / "run-1" / "run-state.json").write_text("{}", encoding="utf-8")
    (vault / "_meta").mkdir(parents=True)
    (vault / "_meta" / "epi-config.yaml").write_text("profile: test\n", encoding="utf-8")
    (vault / "_meta" / "schema.md").write_text("# Schema\n", encoding="utf-8")

    preview = migrate_legacy_epi_roots(vault, dry_run=True)
    result = migrate_legacy_epi_roots(vault)

    assert preview["status"] == "preview"
    assert result["status"] == "migrated"
    assert (vault / "_epi" / "raw" / "papers" / "paper-a" / "metadata.json").is_file()
    assert (vault / "_epi" / "staging" / "papers" / "paper-a" / "wiki-ingest-brief.json").is_file()
    assert (vault / "_epi" / "runs" / "run-1" / "run-state.json").is_file()
    assert (vault / "_epi" / "meta" / "epi-config.yaml").is_file()
    assert (vault / "_meta" / "schema.md").is_file()
    assert not (vault / "_raw").exists()
    assert not (vault / "_staging").exists()
    assert not (vault / "_runs").exists()
    assert (vault / "_epi" / "manifest.json").is_file()
    assert result["manifest_path"].endswith("legacy-roots.json")
