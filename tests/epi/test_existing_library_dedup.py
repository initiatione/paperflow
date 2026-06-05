import json

from epi.filter_candidates import filter_candidates_with_report
from epi.paper_library import load_existing_paper_index


def test_filter_rejects_candidates_already_downloaded_to_raw_library(tmp_path):
    vault = tmp_path / "vault"
    paper_root = vault / "_epi" / "raw" / "existing-paper"
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
