import json

from paper_source.review.generate_reader import generate_reader_outputs
from paper_source.review.run_critic import run_critics


def _write_reader_v2_fixture(tmp_path):
    paper_root = tmp_path / "paper"
    mineru_dir = paper_root / "mineru"
    mineru_dir.mkdir(parents=True)
    (paper_root / "paper.pdf").write_bytes(b"%PDF-1.4\nfixture paper\n")
    (paper_root / "metadata.json").write_text(
        json.dumps(
            {
                "title": "Embodied Navigation Control for Mobile Robots",
                "venue": "IROS",
                "year": 2024,
                "doi": "10.1000/nav",
                "sources": ["fixture", "code", "dataset"],
            }
        ),
        encoding="utf-8",
    )
    (mineru_dir / "paper.md").write_text(
        "# Abstract\n\n"
        "This paper presents embodied navigation control for mobile robots.\n\n"
        "## Method\n\n"
        "The controller combines perception, planning, and feedback control.\n\n"
        "## Results\n\n"
        "The method is evaluated on a navigation benchmark.\n",
        encoding="utf-8",
    )
    return paper_root


def test_reader_v2_emits_role_specific_human_artifacts_and_evidence_map_protocol(tmp_path):
    paper_root = _write_reader_v2_fixture(tmp_path)

    reader_record = generate_reader_outputs(paper_root)

    reader_dir = paper_root / "reader"
    editorial = (reader_dir / "editorial-summary.md").read_text(encoding="utf-8")
    technical = (reader_dir / "technical-reading.md").read_text(encoding="utf-8")
    research = (reader_dir / "research-notes.md").read_text(encoding="utf-8")
    evidence_map = json.loads((reader_dir / "evidence-map.json").read_text(encoding="utf-8"))

    assert "# Editorial Summary" in editorial
    assert "Evidence: source=mineru/paper.md; heading=Abstract" in editorial
    assert "Evidence: source=metadata.json; field=venue" in editorial
    assert "# Technical Reading" in technical
    assert "Evidence: source=mineru/paper.md; heading=Method" in technical
    assert "Evidence: source=metadata.json; field=sources" in technical
    assert "# Research Notes" in research
    assert "Evidence: source=inference; basis=research-fit" in research
    assert "Evidence: source=inference; basis=follow-up-experiments" in research

    assert evidence_map["required_artifacts"] == [
        "reader/reader.md",
        "reader/editorial-summary.md",
        "reader/technical-reading.md",
        "reader/research-notes.md",
        "reader/figures.md",
        "reader/reproducibility.md",
        "reader/implementation-ideas.md",
        "reader/claim-support.json",
    ]
    assert {
        "reader/editorial-summary.md",
        "reader/technical-reading.md",
        "reader/research-notes.md",
    }.issubset({claim["reader_artifact"] for claim in evidence_map["claims"]})
    assert reader_record["output_artifact_hashes"]["editorial-summary.md"]
    assert reader_record["output_artifact_hashes"]["technical-reading.md"]
    assert reader_record["output_artifact_hashes"]["research-notes.md"]
    assert reader_record["output_artifact_hashes"]["evidence-map.json"]
    assert reader_record["output_artifact_hashes"]["claim-support.json"]


def test_reader_v2_emits_source_first_optional_artifact_claims_and_hashes(tmp_path):
    paper_root = _write_reader_v2_fixture(tmp_path)
    mineru_dir = paper_root / "mineru"
    (mineru_dir / "paper.tex").write_text(
        "\\section{Method}\n\\begin{equation}v = \\omega r\\end{equation}\n",
        encoding="utf-8",
    )
    (mineru_dir / "mineru-manifest.json").write_text(
        json.dumps(
            {
                "batch_id": "source-first-batch",
                "outputs": [
                    {
                        "file_name": "paper.pdf",
                        "state": "done",
                        "image_count": 0,
                    }
                ],
                "warnings": ["formula parse should be checked against PDF"],
            }
        ),
        encoding="utf-8",
    )

    reader_record = generate_reader_outputs(paper_root)

    reader_dir = paper_root / "reader"
    technical = (reader_dir / "technical-reading.md").read_text(encoding="utf-8")
    reproducibility = (reader_dir / "reproducibility.md").read_text(encoding="utf-8")
    evidence_map = json.loads((reader_dir / "evidence-map.json").read_text(encoding="utf-8"))
    claim_support = json.loads((reader_dir / "claim-support.json").read_text(encoding="utf-8"))
    sources = {claim["source"] for claim in evidence_map["claims"]}

    assert "Evidence: source=mineru/paper.tex; cue=equation" in technical
    assert "Evidence: source=mineru/mineru-manifest.json; output=paper.pdf; field=state" in technical
    assert "Evidence: source=mineru/mineru-manifest.json; field=warnings" in technical
    assert "Evidence: source=paper.pdf; field=available" in reproducibility
    assert {
        "mineru/paper.tex",
        "mineru/mineru-manifest.json",
        "paper.pdf",
    }.issubset(sources)
    assert reader_record["input_artifact_hashes"]["paper.pdf"]
    assert reader_record["input_artifact_hashes"]["mineru/paper.tex"]
    assert reader_record["input_artifact_hashes"]["mineru/mineru-manifest.json"]
    assert claim_support["support_counts"]["source-grounded"] >= 2
    assert claim_support["support_counts"]["metadata-only"] >= 1


def test_reader_v2_ignores_empty_tex_optional_artifact(tmp_path):
    paper_root = _write_reader_v2_fixture(tmp_path)
    mineru_dir = paper_root / "mineru"
    (mineru_dir / "paper.tex").write_text("", encoding="utf-8")
    (mineru_dir / "mineru-manifest.json").write_text(
        json.dumps(
            {
                "batch_id": "source-first-batch",
                "outputs": [
                    {
                        "file_name": "paper.pdf",
                        "state": "done",
                        "image_count": 0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    reader_record = generate_reader_outputs(paper_root)

    reader_dir = paper_root / "reader"
    technical = (reader_dir / "technical-reading.md").read_text(encoding="utf-8")
    evidence_map = json.loads((reader_dir / "evidence-map.json").read_text(encoding="utf-8"))
    sources = {claim["source"] for claim in evidence_map["claims"]}

    assert "Evidence: source=mineru/paper.tex" not in technical
    assert "mineru/paper.tex" not in reader_record["input_artifact_hashes"]
    assert "mineru/paper.tex" not in sources
    assert "mineru/mineru-manifest.json" in reader_record["input_artifact_hashes"]


def test_critic_rejects_reader_when_required_role_artifact_is_missing(tmp_path):
    paper_root = _write_reader_v2_fixture(tmp_path)
    generate_reader_outputs(paper_root)
    (paper_root / "reader" / "editorial-summary.md").unlink()

    report = run_critics(paper_root)

    assert report["outcome"] == "revise-reader"
    quorum = json.loads((paper_root / "critic" / "critic-quorum.json").read_text(encoding="utf-8"))
    reviewer = next(reviewer for reviewer in quorum["reviewers"] if reviewer["name"] == "reader-quality-critic")
    assert reviewer["verdict"] == "fail"
    assert any("required artifact missing: reader/editorial-summary.md" in item for item in reviewer["evidence"])
