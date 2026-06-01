from epi.reader_outputs import write_role_reader_outputs
from epi.reader_revision_guidance import render_revision_guidance


def test_reader_outputs_module_writes_role_artifacts_and_claim_records(tmp_path):
    reader_dir = tmp_path / "reader"
    reader_dir.mkdir()
    metadata = {
        "venue": "IROS",
        "sources": ["code", "dataset", "simulator"],
    }
    sections = [
        ("Abstract", "This paper presents an embodied control system."),
        ("Method", "The method combines planning and feedback control."),
    ]

    claims = write_role_reader_outputs(
        reader_dir=reader_dir,
        metadata=metadata,
        sections=sections,
        first_claim_index=4,
    )

    editorial = (reader_dir / "editorial-summary.md").read_text(encoding="utf-8")
    technical = (reader_dir / "technical-reading.md").read_text(encoding="utf-8")
    research = (reader_dir / "research-notes.md").read_text(encoding="utf-8")

    assert "## Central Claim" in editorial
    assert "Evidence: source=mineru/<slug>.md; heading=Abstract" in editorial
    assert "Evidence: source=metadata.json; field=venue" in editorial
    assert "## Method Decomposition" in technical
    assert "Evidence: source=mineru/<slug>.md; heading=Method" in technical
    assert "code, dataset, simulator" in technical
    assert "## Fit To Research Direction" in research
    assert "Evidence: source=inference; basis=research-fit" in research

    assert [claim["claim_id"] for claim in claims] == [
        "reader-claim-004",
        "reader-claim-005",
        "reader-claim-006",
        "reader-claim-007",
        "reader-claim-008",
        "reader-claim-009",
        "reader-claim-010",
        "reader-claim-011",
    ]
    assert {claim["reader_role"] for claim in claims} == {
        "nature-sci-editor",
        "peer-reviewer",
        "senior-domain-researcher",
    }
    assert {
        "reader/editorial-summary.md",
        "reader/technical-reading.md",
        "reader/research-notes.md",
    } == {claim["reader_artifact"] for claim in claims}


def test_revision_guidance_renders_role_specific_repair_brief():
    guidance = render_revision_guidance(
        {
            "recommendation": "revise-reader",
            "next_action": "revise-reader",
            "hard_rule": "No critic pass, no compiled wiki write.",
            "role_worklist": [
                {
                    "lens": "peer-reviewer",
                    "heading": "Peer Reviewer",
                    "responsibility": "Audit benchmark and reproducibility discipline.",
                    "target_artifacts": ["reader/technical-reading.md", "reader/reproducibility.md"],
                    "blocking_repairs": [
                        {
                            "check": "benchmark_integrity",
                            "instruction": "Add baseline and metric context.",
                            "target_artifacts": ["reader/technical-reading.md"],
                            "evidence": "missing baseline",
                        }
                    ],
                    "warning_followups": [],
                }
            ],
        }
    )

    assert "# Reader Revision Guidance" in guidance
    assert "## Peer Reviewer" in guidance
    assert "benchmark_integrity" in guidance
    assert "reader/technical-reading.md" in guidance
    assert "No critic pass, no compiled wiki write." in guidance
