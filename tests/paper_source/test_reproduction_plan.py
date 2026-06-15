import json

from paper_source.artifacts import file_sha256
from paper_source.reproduction_plan import build_reproduction_plan
from paper_source.review.run_critic import run_critics


def _seed_repro_warning_paper(tmp_path):
    paper_root = tmp_path / "_raw" / "papers" / "repro-paper"
    mineru_dir = paper_root / "mineru"
    reader_dir = paper_root / "reader"
    mineru_dir.mkdir(parents=True)
    reader_dir.mkdir(parents=True)

    (paper_root / "paper.pdf").write_bytes(b"%PDF-1.4\nfixture\n")
    (paper_root / "metadata.json").write_text(
        json.dumps(
            {
                "slug": "repro-paper",
                "title": "Reproducible Embodied Control",
                "doi": "10.1234/repro",
                "code_url": "https://example.org/code",
                "data_url": "https://example.org/data",
            }
        ),
        encoding="utf-8",
    )
    (mineru_dir / "paper.md").write_text(
        "# Abstract\n\nThe method is an embodied control system with code and data.\n",
        encoding="utf-8",
    )
    (reader_dir / "reader.md").write_text(
        "# Reader\n\n"
        "- Claim 1: The paper proposes an embodied control method.\n"
        "  Evidence: source=mineru/paper.md; heading=Abstract\n",
        encoding="utf-8",
    )
    (reader_dir / "editorial-summary.md").write_text(
        "# Editorial Summary\n\n"
        "## Central Claim\n"
        "- The paper presents an embodied control method.\n"
        "  Evidence: source=mineru/paper.md; heading=Abstract\n\n"
        "## Why It Matters\n"
        "- Inference: relevant to robotics readers.\n"
        "  Evidence: source=inference; basis=editorial-fit\n\n"
        "## Editorial Caveat\n"
        "- Inference: deployment scope should stay bounded.\n"
        "  Evidence: source=inference; basis=scope-caveat\n",
        encoding="utf-8",
    )
    (reader_dir / "technical-reading.md").write_text(
        "# Technical Reading\n\n"
        "## Method Decomposition\n"
        "- Inference: controller, policy, and benchmark loop are separable.\n"
        "  Evidence: source=inference; basis=method-decomposition\n\n"
        "## Reproducibility Hooks\n"
        "- Code and data are visible, but setup details need follow-up.\n"
        "  Evidence: source=metadata.json; field=code_url\n\n"
        "## Reviewer Checkpoint\n"
        "- Inference: reproduction should inspect missing setup details.\n"
        "  Evidence: source=inference; basis=reviewer-checkpoint\n",
        encoding="utf-8",
    )
    (reader_dir / "research-notes.md").write_text(
        "# Research Notes\n\n"
        "## Fit To Research Direction\n"
        "- Inference: useful for embodied control research.\n"
        "  Evidence: source=inference; basis=domain-fit\n\n"
        "## Follow-up Experiments\n"
        "- Inference: reproduce setup details before promotion.\n"
        "  Evidence: source=inference; basis=reproduction-followup\n",
        encoding="utf-8",
    )
    (reader_dir / "figures.md").write_text("# Figures\n\nNo figure claims.\n", encoding="utf-8")
    (reader_dir / "reproducibility.md").write_text(
        "# Reproducibility\n\nCode and data are available; setup details are not found.\n"
        "Evidence: source=metadata.json; field=code_url\n",
        encoding="utf-8",
    )
    (reader_dir / "implementation-ideas.md").write_text(
        "# Implementation Ideas\n\n"
        "- Inference: build a local reproduction checklist before using results.\n"
        "  Evidence: source=inference; basis=implementation-followup\n",
        encoding="utf-8",
    )
    (reader_dir / "evidence-map.json").write_text(
        json.dumps(
            {
                "schema_version": "paper-source-reader-evidence-map-v1",
                "paper_title": "Reproducible Embodied Control",
                "reader_roles": ["nature-sci-editor", "peer-reviewer", "senior-domain-researcher"],
                "claims": [
                    {
                        "claim_id": "claim-001",
                        "reader_role": "nature-sci-editor",
                        "reader_artifact": "reader/reader.md",
                        "claim": "The paper proposes an embodied control method.",
                        "source": "mineru/paper.md",
                        "locator": {"heading": "Abstract"},
                        "evidence_address": "source=mineru/paper.md; heading=Abstract",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return paper_root


def test_build_reproduction_plan_extracts_engineering_gaps():
    plan = build_reproduction_plan(
        "pass",
        [
            {
                "name": "paper-quality-critic",
                "verdict": "pass",
                "warnings": ["engineering_reproducibility: missing model, config, simulator, hardware"],
            }
        ],
        metadata={"slug": "paper", "title": "Paper"},
        hard_rule="No critic pass, no compiled wiki write.",
    )

    missing = {item["item"]: item for item in plan["checklist"] if item["status"] == "missing"}
    assert plan["schema_version"] == "paper-source-reproduction-plan-v1"
    assert plan["next_action"] == "prepare-reproduction-plan"
    assert plan["human_gate_required"] is True
    assert plan["owner_lens"] == "senior-domain-researcher"
    assert {"model", "config", "simulator", "hardware"}.issubset(missing)


def test_run_critics_writes_reproduction_plan_for_warning_followups(tmp_path):
    paper_root = _seed_repro_warning_paper(tmp_path)

    report = run_critics(paper_root)

    plan_path = paper_root / "critic" / "reproduction-plan.json"
    plan_md_path = paper_root / "critic" / "reproduction-plan.md"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan_md = plan_md_path.read_text(encoding="utf-8")
    quorum = json.loads((paper_root / "critic" / "critic-quorum.json").read_text(encoding="utf-8"))

    assert report["reproduction_plan_path"] == str(plan_path)
    assert report["reproduction_plan"]["next_action"] == "prepare-reproduction-plan"
    assert report["output_artifact_hashes"]["reproduction-plan.json"] == file_sha256(plan_path)
    assert report["output_artifact_hashes"]["reproduction-plan.md"] == file_sha256(plan_md_path)
    assert quorum["reproduction_plan_path"] == str(plan_path)
    assert plan["paper_slug"] == "repro-paper"
    assert plan["paper_title"] == "Reproducible Embodied Control"
    assert any(item["item"] == "config" and item["status"] == "missing" for item in plan["checklist"])
    assert any(item["item"] == "simulator" and item["status"] == "missing" for item in plan["checklist"])
    assert "## Senior Domain Researcher Reproduction Tasks" in plan_md
    assert "model" in plan_md
