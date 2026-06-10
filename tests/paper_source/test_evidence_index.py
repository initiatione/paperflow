import json

from paper_source.evidence_index import build_paper_evidence_index, refresh_vault_evidence_index


def _seed_paper(tmp_path, slug="fixture-paper", markdown=None):
    vault = tmp_path / "vault"
    paper_root = vault / "_paper_source" / "raw" / slug
    mineru = paper_root / "mineru"
    mineru.mkdir(parents=True)
    (paper_root / "paper.pdf").write_bytes(b"%PDF-1.4\nfixture\n")
    (paper_root / "metadata.json").write_text(
        json.dumps({"slug": slug, "title": "Fixture Paper", "doi": "10.1000/fixture"}),
        encoding="utf-8",
    )
    (mineru / f"{slug}.md").write_text(
        markdown
        or "# Abstract\n\n[[page:1]]\nThis is abstract evidence.\n\n## Method\n\n[[page:2]]\nThis is method evidence.\n",
        encoding="utf-8",
    )
    (mineru / "paper.tex").write_text("\\section{Method}\n", encoding="utf-8")
    (mineru / "mineru-manifest.json").write_text(json.dumps({"outputs": []}), encoding="utf-8")
    (mineru / "images").mkdir()
    return vault, paper_root


def test_build_paper_evidence_index_chunks_by_section_and_page(tmp_path):
    vault, paper_root = _seed_paper(tmp_path)

    index = build_paper_evidence_index(paper_root, vault_path=vault)

    assert index["schema_version"] == "paper-source-paper-evidence-index-v1"
    assert index["paper_slug"] == "fixture-paper"
    assert index["title"] == "Fixture Paper"
    assert index["source_artifacts"]["mineru_markdown"] == "mineru/fixture-paper.md"
    assert index["input_hashes"]["mineru_markdown"]
    assert len(index["chunks"]) == 2
    assert index["chunks"][0]["page"] == 1
    assert index["chunks"][0]["section_path"] == ["Abstract"]
    assert "abstract evidence" in index["chunks"][0]["text"]
    assert index["chunks"][1]["page"] == 2
    assert index["chunks"][1]["section_path"] == ["Abstract", "Method"]
    assert index["chunks"][1]["source_locator"].startswith("mineru/fixture-paper.md#")
    assert (paper_root / "evidence-index.json").is_file()


def test_build_paper_evidence_index_records_null_page_without_marker(tmp_path):
    vault, paper_root = _seed_paper(
        tmp_path,
        markdown="# Abstract\n\nNo page marker here.\n",
    )

    index = build_paper_evidence_index(paper_root, vault_path=vault)

    assert index["chunks"][0]["page"] is None
    assert "page markers not found" in index["warnings"]


def test_build_paper_evidence_index_treats_empty_tex_as_absent(tmp_path):
    vault, paper_root = _seed_paper(tmp_path)
    (paper_root / "mineru" / "paper.tex").write_text("", encoding="utf-8")

    index = build_paper_evidence_index(paper_root, vault_path=vault)

    assert index["source_artifacts"]["mineru_tex"] is None


def test_refresh_vault_evidence_index_records_paper_entry(tmp_path):
    vault, paper_root = _seed_paper(tmp_path)
    paper_index = build_paper_evidence_index(paper_root, vault_path=vault)

    aggregate = refresh_vault_evidence_index(vault, paper_index)

    aggregate_path = vault / "_paper_source" / "meta" / "evidence-index.json"
    assert aggregate_path.is_file()
    assert aggregate["schema_version"] == "paper-source-vault-evidence-index-v1"
    assert aggregate["papers"][0]["paper_slug"] == "fixture-paper"
    assert aggregate["papers"][0]["evidence_index"] == "_paper_source/raw/fixture-paper/evidence-index.json"
    assert aggregate["papers"][0]["chunk_count"] == len(paper_index["chunks"])
