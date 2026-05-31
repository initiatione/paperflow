import json

from epi.artifacts import file_sha256
from epi.run_critic import run_critics


def _write_role_reader_artifacts(reader_dir) -> None:
    (reader_dir / "editorial-summary.md").write_text(
        "# Editorial Summary\n\n"
        "## Central Claim\n"
        "- The system is relevant to embodied robotics.\n"
        "  Evidence: source=mineru/paper.md; heading=Abstract\n\n"
        "## Why It Matters\n"
        "- The work is framed for an IROS-style robotics audience.\n"
        "  Evidence: source=metadata.json; field=title\n\n"
        "## Editorial Caveat\n"
        "- Inference: deployment scope still needs discipline.\n"
        "  Evidence: source=inference; basis=editorial-caveat\n",
        encoding="utf-8",
    )
    (reader_dir / "technical-reading.md").write_text(
        "# Technical Reading\n\n"
        "## Reproducibility Hooks\n"
        "- Metadata is present, but implementation assets need follow-up.\n"
        "  Evidence: source=metadata.json; field=title\n\n"
        "## Reviewer Checkpoint\n"
        "- Inference: methods need a fuller reviewer pass.\n"
        "  Evidence: source=inference; basis=technical-review-checkpoint\n",
        encoding="utf-8",
    )
    (reader_dir / "research-notes.md").write_text(
        "# Research Notes\n\n"
        "## Fit To Research Direction\n"
        "- Inference: relevant to embodied robotics research.\n"
        "  Evidence: source=inference; basis=research-fit\n\n"
        "## Follow-up Experiments\n"
        "- Inference: useful for a later reproduction queue.\n"
        "  Evidence: source=inference; basis=follow-up-experiments\n",
        encoding="utf-8",
    )


def _write_revision_fixture(tmp_path):
    paper_root = tmp_path / "_raw" / "papers" / "paper"
    mineru_dir = paper_root / "mineru"
    reader_dir = paper_root / "reader"
    mineru_dir.mkdir(parents=True)
    reader_dir.mkdir(parents=True)

    (paper_root / "paper.pdf").write_bytes(b"%PDF-1.4\nfixture paper\n")
    (paper_root / "metadata.json").write_text(
        json.dumps({"slug": "paper", "title": "Embodied Robotics Fixture"}),
        encoding="utf-8",
    )
    (mineru_dir / "paper.md").write_text(
        "# Abstract\n\nThe system is relevant to embodied robotics.\n",
        encoding="utf-8",
    )
    (reader_dir / "reader.md").write_text(
        "# Reader\n\n"
        "- Claim 1: The paper proposes an embodied robotics system.\n"
        "  Evidence: source=mineru/paper.md; heading=Abstract\n",
        encoding="utf-8",
    )
    (reader_dir / "figures.md").write_text("# Figures\n\nNo figure claims.\n", encoding="utf-8")
    (reader_dir / "reproducibility.md").write_text(
        "# Reproducibility\n\nNo code or data availability was found.\n",
        encoding="utf-8",
    )
    _write_role_reader_artifacts(reader_dir)
    (reader_dir / "evidence-map.json").write_text(
        json.dumps(
            {
                "schema_version": "epi-reader-evidence-map-v1",
                "paper_title": "Embodied Robotics Fixture",
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
                        "claim": "The system is relevant to embodied robotics.",
                        "source": "mineru/paper.md",
                        "locator": {"heading": "Abstract"},
                        "evidence_address": "source=mineru/paper.md; heading=Abstract",
                    },
                    {
                        "claim_id": "reader-claim-002",
                        "reader_role": "peer-reviewer",
                        "reader_artifact": "reader/technical-reading.md",
                        "claim": "Metadata is present.",
                        "source": "metadata.json",
                        "locator": {"field": "title"},
                        "evidence_address": "source=metadata.json; field=title",
                    },
                    {
                        "claim_id": "reader-claim-003",
                        "reader_role": "senior-domain-researcher",
                        "reader_artifact": "reader/research-notes.md",
                        "claim": "Reproduction queue potential.",
                        "source": "inference",
                        "locator": {"basis": "follow-up-experiments"},
                        "evidence_address": "source=inference; basis=follow-up-experiments",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return paper_root


def test_run_critics_writes_reader_revision_plan_with_role_worklist(tmp_path):
    paper_root = _write_revision_fixture(tmp_path)

    report = run_critics(paper_root)

    critic_dir = paper_root / "critic"
    plan_path = critic_dir / "reader-revision-plan.json"
    plan_md_path = critic_dir / "reader-revision-plan.md"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan_md = plan_md_path.read_text(encoding="utf-8")
    quorum = json.loads((critic_dir / "critic-quorum.json").read_text(encoding="utf-8"))

    assert report["outcome"] == "revise-reader"
    assert report["reader_revision_plan_path"] == str(plan_path)
    assert report["output_artifact_hashes"]["reader-revision-plan.json"] == file_sha256(plan_path)
    assert report["output_artifact_hashes"]["reader-revision-plan.md"] == file_sha256(plan_md_path)
    assert quorum["reader_revision_plan_path"] == str(plan_path)
    assert plan["schema_version"] == "epi-reader-revision-plan-v1"
    assert plan["next_action"] == "revise-reader"
    assert plan["hard_rule"] == "No critic pass, no compiled wiki write."

    assert any(
        item["reviewer"] == "paper-quality-critic"
        and item["check"] == "paper_identity"
        and item["lens"] == "nature-sci-editor+senior-domain-researcher"
        and "metadata.json" in item["target_artifacts"]
        for item in plan["blocking_repairs"]
    )
    assert any(
        item["reviewer"] == "peer-review-methods-critic"
        and item["check"] == "role_artifact_contract"
        and item["lens"] == "peer-reviewer"
        and item["target_artifacts"] == ["reader/technical-reading.md"]
        and "## Method Decomposition" in item["evidence"]
        for item in plan["blocking_repairs"]
    )
    assert any(
        item["check"] == "engineering_reproducibility"
        and item["promotion_blocking"] is False
        and "reader/reproducibility.md" in item["target_artifacts"]
        for item in plan["warning_followups"]
    )

    worklist = {item["lens"]: item for item in plan["role_worklist"]}
    assert worklist["nature-sci-editor"]["target_artifacts"] == ["reader/editorial-summary.md"]
    assert worklist["peer-reviewer"]["target_artifacts"] == [
        "reader/technical-reading.md",
        "reader/reproducibility.md",
    ]
    assert worklist["senior-domain-researcher"]["target_artifacts"] == [
        "reader/research-notes.md",
        "reader/implementation-ideas.md",
    ]
    assert worklist["peer-reviewer"]["blocking_repairs"]
    assert worklist["peer-reviewer"]["warning_followups"]
    assert "## Peer Reviewer" in plan_md
    assert "reader/technical-reading.md" in plan_md
    assert "engineering_reproducibility" in plan_md
