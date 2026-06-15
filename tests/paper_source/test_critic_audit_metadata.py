import json

import pytest

from paper_source.artifacts import file_sha256
from paper_source.review.run_critic import run_critics
from paper_source.stage_wiki import stage_paper


EXPECTED_TOOL_VERSIONS = {
    "critic_pipeline": "paper-source-local-static-v1",
}


def _write_role_reader_artifacts(reader_dir, *, evidence_heading: str) -> None:
    (reader_dir / "editorial-summary.md").write_text(
        "# Editorial Summary\n\n"
        "## Central Claim\n"
        "- Parsed claim.\n"
        f"  Evidence: source=mineru/paper.md; heading={evidence_heading}\n\n"
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
        "- Parsed method claim.\n"
        f"  Evidence: source=mineru/paper.md; heading={evidence_heading}\n\n"
        "## Reproducibility Hooks\n"
        "- Metadata is present.\n"
        "  Evidence: source=metadata.json; field=venue\n\n"
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


def _write_critic_fixture(tmp_path, *, reader_text: str) -> tuple:
    paper_root = tmp_path / "_raw" / "papers" / "paper"
    critic_dir = paper_root / "critic"
    mineru_dir = paper_root / "mineru"
    reader_dir = paper_root / "reader"
    critic_dir.mkdir(parents=True)
    mineru_dir.mkdir(parents=True)
    reader_dir.mkdir(parents=True)
    (paper_root / "paper.pdf").write_bytes(b"%PDF-1.4\nfixture paper\n")
    (paper_root / "metadata.json").write_text(
        json.dumps({"slug": "paper", "title": "Fixture Paper", "doi": "10.1000/fixture", "venue": "IROS"}),
        encoding="utf-8",
    )
    (mineru_dir / "paper.md").write_text("# Paper\n\nParsed claim.\n", encoding="utf-8")
    (reader_dir / "reader.md").write_text(reader_text, encoding="utf-8")
    _write_role_reader_artifacts(reader_dir, evidence_heading="Paper")
    (reader_dir / "evidence-map.json").write_text(
        json.dumps(
            {
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
                        "claim": "Parsed claim.",
                        "source": "mineru/paper.md",
                        "locator": {"heading": "Paper"},
                        "evidence_address": "source=mineru/paper.md; heading=Paper",
                    },
                    {
                        "claim_id": "reader-claim-002",
                        "reader_role": "peer-reviewer",
                        "reader_artifact": "reader/reader.md",
                        "claim": "Venue metadata is present.",
                        "source": "metadata.json",
                        "locator": {"field": "venue"},
                        "evidence_address": "source=metadata.json; field=venue",
                    },
                    {
                        "claim_id": "reader-claim-003",
                        "reader_role": "senior-domain-researcher",
                        "reader_artifact": "reader/reader.md",
                        "claim": "Transfer idea requires researcher judgment.",
                        "source": "inference",
                        "locator": {"basis": "implementation-ideas"},
                        "evidence_address": "source=inference; basis=implementation-ideas",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return paper_root, critic_dir


def test_run_critics_writes_audit_metadata_for_pass(tmp_path):
    paper_root, critic_dir = _write_critic_fixture(
        tmp_path,
        reader_text="# Reader\n\n- Claim 1: Parsed claim.\n  Evidence: source=mineru/paper.md; heading=Paper\n",
    )

    report = run_critics(paper_root)
    quorum = json.loads((critic_dir / "critic-quorum.json").read_text(encoding="utf-8"))

    assert report["outcome"] == "pass"
    assert report["started_at"]
    assert report["finished_at"]
    assert report["exit_status"] == 0
    assert report["tool_versions"] == EXPECTED_TOOL_VERSIONS
    assert report["input_artifact_hashes"] == {
        "paper.pdf": file_sha256(paper_root / "paper.pdf"),
        "metadata.json": file_sha256(paper_root / "metadata.json"),
        "mineru/paper.md": file_sha256(paper_root / "mineru" / "paper.md"),
        "reader/reader.md": file_sha256(paper_root / "reader" / "reader.md"),
        "reader/editorial-summary.md": file_sha256(paper_root / "reader" / "editorial-summary.md"),
        "reader/technical-reading.md": file_sha256(paper_root / "reader" / "technical-reading.md"),
        "reader/research-notes.md": file_sha256(paper_root / "reader" / "research-notes.md"),
        "reader/evidence-map.json": file_sha256(paper_root / "reader" / "evidence-map.json"),
    }
    assert report["output_artifact_hashes"]["critic-quorum.json"] == file_sha256(critic_dir / "critic-quorum.json")
    assert report["output_artifact_hashes"]["paper-quality-critic.md"] == file_sha256(
        critic_dir / "paper-quality-critic.md"
    )
    assert report["output_artifact_hashes"]["parse-quality-critic.md"] == file_sha256(
        critic_dir / "parse-quality-critic.md"
    )
    assert report["output_artifact_hashes"]["reader-quality-critic.md"] == file_sha256(
        critic_dir / "reader-quality-critic.md"
    )
    assert report["output_artifact_hashes"]["editorial-significance-critic.md"] == file_sha256(
        critic_dir / "editorial-significance-critic.md"
    )
    assert report["output_artifact_hashes"]["peer-review-methods-critic.md"] == file_sha256(
        critic_dir / "peer-review-methods-critic.md"
    )
    assert report["output_artifact_hashes"]["domain-fit-critic.md"] == file_sha256(
        critic_dir / "domain-fit-critic.md"
    )

    assert quorum["final_outcome"] == "pass"
    assert quorum["started_at"]
    assert quorum["finished_at"]
    assert quorum["exit_status"] == 0
    assert quorum["tool_versions"] == EXPECTED_TOOL_VERSIONS
    assert quorum["input_artifact_hashes"] == report["input_artifact_hashes"]
    assert quorum["output_artifact_hashes"]["paper-quality-critic.md"] == file_sha256(
        critic_dir / "paper-quality-critic.md"
    )
    assert quorum["output_artifact_hashes"]["parse-quality-critic.md"] == file_sha256(
        critic_dir / "parse-quality-critic.md"
    )
    assert quorum["output_artifact_hashes"]["reader-quality-critic.md"] == file_sha256(
        critic_dir / "reader-quality-critic.md"
    )


def test_run_critics_writes_audit_metadata_for_revise_reader(tmp_path):
    paper_root, critic_dir = _write_critic_fixture(
        tmp_path,
        reader_text="# Reader\n\n- Claim 1: Parsed claim without evidence marker.\n",
    )

    report = run_critics(paper_root)
    quorum = json.loads((critic_dir / "critic-quorum.json").read_text(encoding="utf-8"))

    assert report["outcome"] == "revise-reader"
    assert report["started_at"]
    assert report["finished_at"]
    # Non-pass is a completed review verdict, not a runtime crash.
    assert report["exit_status"] == 1
    assert report["next_action"] == "revise-reader"
    assert report["tool_versions"] == EXPECTED_TOOL_VERSIONS
    assert report["input_artifact_hashes"] == {
        "paper.pdf": file_sha256(paper_root / "paper.pdf"),
        "metadata.json": file_sha256(paper_root / "metadata.json"),
        "mineru/paper.md": file_sha256(paper_root / "mineru" / "paper.md"),
        "reader/reader.md": file_sha256(paper_root / "reader" / "reader.md"),
        "reader/editorial-summary.md": file_sha256(paper_root / "reader" / "editorial-summary.md"),
        "reader/technical-reading.md": file_sha256(paper_root / "reader" / "technical-reading.md"),
        "reader/research-notes.md": file_sha256(paper_root / "reader" / "research-notes.md"),
        "reader/evidence-map.json": file_sha256(paper_root / "reader" / "evidence-map.json"),
    }
    assert report["output_artifact_hashes"]["critic-quorum.json"] == file_sha256(critic_dir / "critic-quorum.json")
    assert report["output_artifact_hashes"]["paper-quality-critic.md"] == file_sha256(
        critic_dir / "paper-quality-critic.md"
    )
    assert report["output_artifact_hashes"]["parse-quality-critic.md"] == file_sha256(
        critic_dir / "parse-quality-critic.md"
    )
    assert report["output_artifact_hashes"]["reader-quality-critic.md"] == file_sha256(
        critic_dir / "reader-quality-critic.md"
    )

    assert quorum["final_outcome"] == "revise-reader"
    assert quorum["started_at"]
    assert quorum["finished_at"]
    # Quorum completed and produced a non-promotable decision.
    assert quorum["exit_status"] == 1
    assert quorum["tool_versions"] == EXPECTED_TOOL_VERSIONS
    assert quorum["input_artifact_hashes"] == report["input_artifact_hashes"]
    assert quorum["output_artifact_hashes"]["paper-quality-critic.md"] == file_sha256(
        critic_dir / "paper-quality-critic.md"
    )
    assert quorum["output_artifact_hashes"]["parse-quality-critic.md"] == file_sha256(
        critic_dir / "parse-quality-critic.md"
    )
    assert quorum["output_artifact_hashes"]["reader-quality-critic.md"] == file_sha256(
        critic_dir / "reader-quality-critic.md"
    )


def test_run_critics_nonpass_result_is_not_promotable(tmp_path):
    vault = tmp_path / "vault"
    paper_root, _critic_dir = _write_critic_fixture(
        vault,
        reader_text="# Reader\n\n- Claim 1: Parsed claim without evidence marker.\n",
    )

    report = run_critics(paper_root)

    assert report["outcome"] == "revise-reader"
    assert report["exit_status"] == 1
    assert report["next_action"] == "revise-reader"

    with pytest.raises(ValueError, match="critic outcome"):
        stage_paper(vault, "paper", paper_root)

    assert not (vault / "_staging" / "papers" / "paper").exists()
