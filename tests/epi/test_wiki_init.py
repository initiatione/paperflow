import json
import subprocess

from epi.wiki_init import initialize_paper_wiki


def test_initialize_paper_wiki_creates_required_layout(tmp_path):
    vault = tmp_path / "paper-research-wiki"

    created = initialize_paper_wiki(vault)

    expected_dirs = [
        "_raw/papers",
        "_staging/papers",
        "_quarantine/papers",
        "_runs",
        "_evolution/proposals",
        "_evolution/pending",
        "_evolution/active",
        "_evolution/archive",
        "_evolution/rejected",
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
    assert "mineru/paper.md" in manifest["must_read_source_artifacts"]
    assert "mineru/images/*" in manifest["must_read_source_artifacts"]
    assert "wiki-ingest-brief.json" in manifest["handoff_artifacts"]
    assert (vault / "AGENTS.md").is_file()
    assert (vault / "_meta" / "agent-operating-contract.md").is_file()
    assert (vault / "_meta" / "schema.md").is_file()
    assert (vault / "_meta" / "taxonomy.md").is_file()
    assert (vault / "_meta" / "directory-structure.md").is_file()
    assert "Source-first paper ingest" in (vault / "AGENTS.md").read_text(encoding="utf-8")
    assert "mineru/paper.tex" in (vault / "_meta" / "agent-operating-contract.md").read_text(encoding="utf-8")
    assert "figures/tables/images" in (vault / "_meta" / "schema.md").read_text(encoding="utf-8")
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


def test_initialize_paper_wiki_preserves_existing_git_repo(tmp_path):
    vault = tmp_path / "paper-research-wiki"
    vault.mkdir(parents=True)
    subprocess.run(["git", "-C", str(vault), "init"], check=True, capture_output=True, text=True)

    created = initialize_paper_wiki(vault)

    assert ".git" not in created
    assert (vault / ".git").is_dir()
