import json

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
    assert "index.md" in created
