from epi.source_bundle_audit import audit_source_bundle


def _seed_source_bundle(paper_root, slug="fixture-paper"):
    paper_root.mkdir(parents=True, exist_ok=True)
    (paper_root / "paper.pdf").write_bytes(b"%PDF-1.4\nfixture\n")
    (paper_root / "metadata.json").write_text("{}", encoding="utf-8")
    mineru = paper_root / "mineru"
    mineru.mkdir(parents=True, exist_ok=True)
    (mineru / f"{slug}.md").write_text("# Fixture\n", encoding="utf-8")
    (mineru / "paper.tex").write_text("\\section{Fixture}\n", encoding="utf-8")
    (mineru / "mineru-manifest.json").write_text("{}", encoding="utf-8")
    image_dir = mineru / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    (image_dir / "figure-1.png").write_bytes(b"image")


def test_audit_source_bundle_reports_complete_bundle(tmp_path):
    paper_root = tmp_path / "fixture-paper"
    _seed_source_bundle(paper_root)

    audit = audit_source_bundle(paper_root)

    assert audit["status"] == "complete"
    assert audit["complete"] is True
    assert audit["missing_artifacts"] == []
    assert audit["mineru_markdown"] == "mineru/fixture-paper.md"
    assert audit["artifact_records"]["paper.pdf"]["exists"] is True
    assert audit["artifact_records"]["mineru/images/*"]["file_count"] == 1


def test_audit_source_bundle_reports_missing_disk_artifacts(tmp_path):
    paper_root = tmp_path / "fixture-paper"
    _seed_source_bundle(paper_root)
    (paper_root / "paper.pdf").unlink()
    (paper_root / "mineru" / "mineru-manifest.json").unlink()
    for image in (paper_root / "mineru" / "images").glob("*"):
        image.unlink()

    audit = audit_source_bundle(paper_root)

    assert audit["status"] == "incomplete"
    assert audit["complete"] is False
    assert audit["missing_artifacts"] == [
        "paper.pdf",
        "mineru/images/*",
        "mineru/mineru-manifest.json",
    ]
    assert audit["artifact_records"]["paper.pdf"]["exists"] is False
    assert audit["artifact_records"]["mineru/images/*"]["file_count"] == 0
