import json

import pytest

from paper_source.review.run_critic import run_critics
from paper_source.stage_wiki import stage_paper


def _write_role_reader_artifacts(reader_dir) -> None:
    (reader_dir / "editorial-summary.md").write_text(
        "# Editorial Summary\n\n"
        "## Central Claim\n"
        "- Traceable abstract claim.\n"
        "  Evidence: source=mineru/paper.md; heading=Abstract\n\n"
        "## Why It Matters\n"
        "- Venue/context: IROS.\n"
        "  Evidence: source=metadata.json; field=venue\n\n"
        "## Editorial Caveat\n"
        "- Inference: scope needs critic review.\n"
        "  Evidence: source=inference; basis=editorial-caveat\n",
        encoding="utf-8",
    )
    (reader_dir / "technical-reading.md").write_text(
        "# Technical Reading\n\n"
        "## Method Decomposition\n"
        "- Traceable methods claim.\n"
        "  Evidence: source=mineru/paper.md; heading=Methods\n\n"
        "## Reproducibility Hooks\n"
        "- Source availability claim.\n"
        "  Evidence: source=metadata.json; field=sources\n\n"
        "## Reviewer Checkpoint\n"
        "- Inference: benchmark details need checking.\n"
        "  Evidence: source=inference; basis=technical-review-checkpoint\n",
        encoding="utf-8",
    )
    (reader_dir / "research-notes.md").write_text(
        "# Research Notes\n\n"
        "## Fit To Research Direction\n"
        "- Inference: relevant to robotics research.\n"
        "  Evidence: source=inference; basis=research-fit\n\n"
        "## Follow-up Experiments\n"
        "- Inference: use for future ablations.\n"
        "  Evidence: source=inference; basis=follow-up-experiments\n",
        encoding="utf-8",
    )


def _write_traceability_fixture(
    tmp_path,
    *,
    reader_text: str,
    figures_text: str | None = None,
    reproducibility_text: str | None = None,
    evidence_map: dict | None = None,
    write_evidence_map: bool = True,
):
    vault = tmp_path / "vault"
    paper_root = vault / "_raw" / "papers" / "paper"
    mineru_dir = paper_root / "mineru"
    reader_dir = paper_root / "reader"
    images_dir = mineru_dir / "images"

    images_dir.mkdir(parents=True)
    reader_dir.mkdir(parents=True)

    (paper_root / "paper.pdf").write_bytes(b"%PDF-1.4\nfixture paper\n")
    (paper_root / "metadata.json").write_text(
        json.dumps(
            {
                "slug": "paper",
                "title": "Fixture Paper",
                "doi": "10.1000/fixture",
                "venue": "IROS",
                "sources": ["code", "appendix"],
            }
        ),
        encoding="utf-8",
    )
    (mineru_dir / "paper.md").write_text(
        "# Abstract\n\nTraceable abstract claim.\n\n## Methods\n\nTraceable methods claim.\n",
        encoding="utf-8",
    )
    (images_dir / "figure-1.png").write_bytes(b"png")
    (reader_dir / "reader.md").write_text(reader_text, encoding="utf-8")
    (reader_dir / "figures.md").write_text(
        figures_text
        or (
            "# Figures\n\n"
            "- Figure claim.\n"
            "  Evidence: source=mineru/images; image=figure-1.png\n"
        ),
        encoding="utf-8",
    )
    (reader_dir / "reproducibility.md").write_text(
        reproducibility_text
        or (
            "# Reproducibility\n\n"
            "- Source availability claim.\n"
            "  Evidence: source=metadata.json; field=sources\n"
        ),
        encoding="utf-8",
    )
    _write_role_reader_artifacts(reader_dir)
    if write_evidence_map:
        payload = evidence_map or {
            "schema_version": "paper-source-reader-evidence-map-v1",
            "paper_title": "Fixture Paper",
            "reader_roles": [
                "nature-sci-editor",
                "peer-reviewer",
                "senior-domain-researcher",
            ],
            "claims": [
                {
                    "claim_id": "reader-claim-001",
                    "reader_role": "nature-sci-editor",
                    "reader_artifact": "reader/reader.md",
                    "claim": "Traceable abstract claim.",
                    "source": "mineru/paper.md",
                    "locator": {"heading": "Abstract"},
                    "evidence_address": "source=mineru/paper.md; heading=Abstract",
                },
                {
                    "claim_id": "reader-claim-002",
                    "reader_role": "peer-reviewer",
                    "reader_artifact": "reader/reproducibility.md",
                    "claim": "Source availability claim.",
                    "source": "metadata.json",
                    "locator": {"field": "sources"},
                    "evidence_address": "source=metadata.json; field=sources",
                },
                {
                    "claim_id": "reader-claim-003",
                    "reader_role": "senior-domain-researcher",
                    "reader_artifact": "reader/reader.md",
                    "claim": "Transfer idea.",
                    "source": "inference",
                    "locator": {"basis": "implementation-ideas"},
                    "evidence_address": "source=inference; basis=implementation-ideas",
                },
            ],
        }
        (reader_dir / "evidence-map.json").write_text(json.dumps(payload), encoding="utf-8")
    return vault, paper_root


def test_run_critics_passes_when_reader_claims_use_traceable_evidence_addresses(tmp_path):
    _vault, paper_root = _write_traceability_fixture(
        tmp_path,
        reader_text=(
            "# Reader\n\n"
            "- Claim 1: abstract grounding.\n"
            "  Evidence: source=mineru/paper.md; heading=Abstract\n"
            "- Claim 2: metadata grounding.\n"
            "  Evidence: source=metadata.json; field=title\n"
            "- Claim 3: figure grounding.\n"
            "  Evidence: source=mineru/images; image=figure-1.png\n"
            "- Claim 4: transfer idea.\n"
            "  Evidence: source=inference; basis=implementation-ideas\n"
        ),
    )

    report = run_critics(paper_root)

    assert report["outcome"] == "pass"
    assert report["next_action"] == "stage"
    assert report["hard_rule"] == "No critic pass, no compiled wiki write."


@pytest.mark.parametrize(
    ("bad_evidence", "expected_fragment"),
    [
        ("source=mineru/paper.md; heading=Results", "heading=Results"),
        ("source=metadata.json; field=publisher", "field=publisher"),
        ("source=mineru/images; image=figure-2.png", "image=figure-2.png"),
    ],
)
def test_run_critics_revises_reader_when_evidence_address_points_to_missing_artifact(
    tmp_path,
    bad_evidence: str,
    expected_fragment: str,
):
    _vault, paper_root = _write_traceability_fixture(
        tmp_path,
        reader_text=f"# Reader\n\n- Claim 1: broken evidence.\n  Evidence: {bad_evidence}\n",
    )

    report = run_critics(paper_root)

    assert report["outcome"] == "revise-reader"
    assert report["next_action"] == "revise-reader"
    reviewer = next(
        reviewer
        for reviewer in json.loads((paper_root / "critic" / "critic-quorum.json").read_text(encoding="utf-8"))["reviewers"]
        if reviewer["name"] == "reader-quality-critic"
    )
    assert reviewer["verdict"] == "fail"
    assert any(expected_fragment in line for line in reviewer["evidence"])


def test_nonpass_critic_result_with_bad_evidence_cannot_be_staged(tmp_path):
    vault, paper_root = _write_traceability_fixture(
        tmp_path,
        reader_text=(
            "# Reader\n\n"
            "- Claim 1: missing heading.\n"
            "  Evidence: source=mineru/paper.md; heading=Results\n"
        ),
    )

    report = run_critics(paper_root)

    assert report["outcome"] == "revise-reader"

    with pytest.raises(ValueError, match="critic outcome"):
        stage_paper(vault, "paper", paper_root)

    assert not (vault / "_staging" / "papers" / "paper").exists()


def test_run_critics_revises_reader_when_figures_or_reproducibility_contains_bad_evidence(tmp_path):
    _vault, paper_root = _write_traceability_fixture(
        tmp_path,
        reader_text=(
            "# Reader\n\n"
            "- Claim 1: abstract grounding.\n"
            "  Evidence: source=mineru/paper.md; heading=Abstract\n"
        ),
        figures_text=(
            "# Figures\n\n"
            "- Figure claim with broken address.\n"
            "  Evidence: source=mineru/images; image=figure-2.png\n"
        ),
    )

    report = run_critics(paper_root)

    assert report["outcome"] == "revise-reader"
    reviewer = next(
        reviewer
        for reviewer in json.loads((paper_root / "critic" / "critic-quorum.json").read_text(encoding="utf-8"))["reviewers"]
        if reviewer["name"] == "reader-quality-critic"
    )
    assert reviewer["verdict"] == "fail"
    assert any("image=figure-2.png" in line for line in reviewer["evidence"])


def test_run_critics_revises_reader_when_evidence_map_is_missing(tmp_path):
    _vault, paper_root = _write_traceability_fixture(
        tmp_path,
        reader_text=(
            "# Reader\n\n"
            "- Claim 1: abstract grounding.\n"
            "  Evidence: source=mineru/paper.md; heading=Abstract\n"
        ),
        write_evidence_map=False,
    )

    report = run_critics(paper_root)

    assert report["outcome"] == "revise-reader"
    reviewer = next(
        reviewer
        for reviewer in json.loads((paper_root / "critic" / "critic-quorum.json").read_text(encoding="utf-8"))["reviewers"]
        if reviewer["name"] == "reader-quality-critic"
    )
    assert reviewer["verdict"] == "fail"
    assert any("reader/evidence-map.json missing" in line for line in reviewer["evidence"])


def test_run_critics_revises_reader_when_evidence_map_points_to_missing_artifact(tmp_path):
    _vault, paper_root = _write_traceability_fixture(
        tmp_path,
        reader_text=(
            "# Reader\n\n"
            "- Claim 1: abstract grounding.\n"
            "  Evidence: source=mineru/paper.md; heading=Abstract\n"
        ),
        evidence_map={
            "schema_version": "paper-source-reader-evidence-map-v1",
            "paper_title": "Fixture Paper",
            "reader_roles": [
                "nature-sci-editor",
                "peer-reviewer",
                "senior-domain-researcher",
            ],
            "claims": [
                {
                    "claim_id": "reader-claim-001",
                    "reader_role": "nature-sci-editor",
                    "reader_artifact": "reader/reader.md",
                    "claim": "Broken metadata claim.",
                    "source": "metadata.json",
                    "locator": {"field": "publisher"},
                    "evidence_address": "source=metadata.json; field=publisher",
                },
                {
                    "claim_id": "reader-claim-002",
                    "reader_role": "peer-reviewer",
                    "reader_artifact": "reader/reader.md",
                    "claim": "Traceable abstract claim.",
                    "source": "mineru/paper.md",
                    "locator": {"heading": "Abstract"},
                    "evidence_address": "source=mineru/paper.md; heading=Abstract",
                },
                {
                    "claim_id": "reader-claim-003",
                    "reader_role": "senior-domain-researcher",
                    "reader_artifact": "reader/reader.md",
                    "claim": "Transfer idea.",
                    "source": "inference",
                    "locator": {"basis": "implementation-ideas"},
                    "evidence_address": "source=inference; basis=implementation-ideas",
                },
            ],
        },
    )

    report = run_critics(paper_root)

    assert report["outcome"] == "revise-reader"
    reviewer = next(
        reviewer
        for reviewer in json.loads((paper_root / "critic" / "critic-quorum.json").read_text(encoding="utf-8"))["reviewers"]
        if reviewer["name"] == "reader-quality-critic"
    )
    assert reviewer["verdict"] == "fail"
    assert any("reader/evidence-map.json" in line and "field=publisher" in line for line in reviewer["evidence"])
