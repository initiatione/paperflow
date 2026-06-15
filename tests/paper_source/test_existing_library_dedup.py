import json

from paper_source.filter_candidates import filter_candidates_with_report
from paper_source.paper_library import load_existing_paper_index


def test_filter_rejects_candidates_already_downloaded_to_raw_library(tmp_path):
    vault = tmp_path / "vault"
    paper_root = vault / "_paper_source" / "raw" / "existing-paper"
    paper_root.mkdir(parents=True)
    (paper_root / "metadata.json").write_text(
        json.dumps(
            {
                "slug": "existing-paper",
                "title": "Existing AUV Control Paper",
                "doi": "10.1000/existing",
            }
        ),
        encoding="utf-8",
    )

    index = load_existing_paper_index(vault)
    report = filter_candidates_with_report(
        [
            {
                "title": "Existing AUV Control Paper",
                "doi": "10.1000/existing",
                "abstract": "AUV control method with experiments.",
                "pdf_url": "https://example.org/paper.pdf",
            },
            {
                "title": "New AUV Control Paper",
                "doi": "10.1000/new",
                "abstract": "AUV control method with experiments.",
                "pdf_url": "https://example.org/new.pdf",
            },
        ],
        domains=["control"],
        require_pdf=True,
        existing_library_index=index,
    )

    assert [item["title"] for item in report["kept"]] == ["New AUV Control Paper"]
    assert report["rejected"][0]["filter_reasons"] == ["already_in_library:existing-paper"]
    assert report["rejected"][0]["existing_library_match"]["key"] == "doi:10.1000/existing"


def test_filter_rejects_candidates_already_deposited_in_reference_index(tmp_path):
    vault = tmp_path / "vault"
    meta = vault / "_meta"
    meta.mkdir(parents=True)
    (meta / "reference-index.json").write_text(
        json.dumps(
            {
                "schema_version": "paper-research-reference-index-v1",
                "entries": [
                    {
                        "title": "Learning to Swim: Reinforcement Learning for 6-DOF Control",
                        "normalized_title": "learning to swim reinforcement learning for 6 dof control",
                        "page": "references/learning-to-swim-isaac-lab-auv-rl-control.md",
                        "source_id": "learning-to-swim-reinforcement-learning-for-6-dof-control",
                        "doi": None,
                        "arxiv_id": "2410.00120v2",
                        "arxiv_base_id": "2410.00120",
                        "dedupe_keys": [
                            "arxiv:2410.00120",
                            "source_id:learning-to-swim-reinforcement-learning-for-6-dof-control",
                            "title:learning to swim reinforcement learning for 6 dof control",
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    index = load_existing_paper_index(vault)
    report = filter_candidates_with_report(
        [
            {
                "title": "Learning to Swim: Reinforcement Learning for 6-DOF Control",
                "arxiv_id": "2410.00120v3",
                "abstract": "AUV 6-DOF reinforcement learning control with experiments.",
                "pdf_url": "https://arxiv.org/pdf/2410.00120v3",
            }
        ],
        domains=["AUV"],
        require_pdf=True,
        existing_library_index=index,
    )

    assert report["kept"] == []
    assert report["rejected"][0]["filter_reasons"] == [
        "already_in_wiki:references/learning-to-swim-isaac-lab-auv-rl-control.md"
    ]
    assert report["rejected"][0]["existing_library_match"]["source_type"] == "wiki_reference_index"
    assert report["rejected"][0]["existing_library_match"]["key"] == "arxiv:2410.00120"
    assert index["wiki_count"] == 1
    assert index["raw_count"] == 0


def test_reference_index_match_takes_precedence_over_raw_library_match(tmp_path):
    vault = tmp_path / "vault"
    meta = vault / "_meta"
    meta.mkdir(parents=True)
    (meta / "reference-index.json").write_text(
        json.dumps(
            {
                "schema_version": "paper-research-reference-index-v1",
                "entries": [
                    {
                        "title": "Deposited AUV Control Paper",
                        "page": "references/deposited-auv-control-paper.md",
                        "source_id": "deposited-auv-control-paper",
                        "doi": "10.1000/shared",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    paper_root = vault / "_paper_source" / "raw" / "raw-copy"
    paper_root.mkdir(parents=True)
    (paper_root / "metadata.json").write_text(
        json.dumps({"slug": "raw-copy", "title": "Deposited AUV Control Paper", "doi": "10.1000/shared"}),
        encoding="utf-8",
    )

    index = load_existing_paper_index(vault)
    match = filter_candidates_with_report(
        [
            {
                "title": "Deposited AUV Control Paper",
                "doi": "https://doi.org/10.1000/shared",
                "abstract": "AUV control method with experiments.",
                "pdf_url": "https://example.org/paper.pdf",
            }
        ],
        domains=["control"],
        require_pdf=True,
        existing_library_index=index,
    )["rejected"][0]

    assert match["filter_reasons"] == ["already_in_wiki:references/deposited-auv-control-paper.md"]
    assert match["existing_library_match"]["source_type"] == "wiki_reference_index"
