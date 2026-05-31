import json

from epi.generate_reader import generate_reader_outputs
from epi.run_critic import run_critics


def _write_role_critic_fixture(tmp_path):
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
                "sources": ["fixture", "code", "dataset", "simulator", "hardware", "model", "config"],
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
        "The method is evaluated on a navigation benchmark with a baseline and reward metric.\n",
        encoding="utf-8",
    )
    return paper_root


def test_critic_quorum_includes_role_specific_reviewers_for_reader_v2_outputs(tmp_path):
    paper_root = _write_role_critic_fixture(tmp_path)
    generate_reader_outputs(paper_root)

    report = run_critics(paper_root)
    quorum = json.loads((paper_root / "critic" / "critic-quorum.json").read_text(encoding="utf-8"))

    assert report["outcome"] == "pass"
    assert report["reviewer_count"] == 6
    assert [reviewer["name"] for reviewer in quorum["reviewers"]] == [
        "paper-quality-critic",
        "parse-quality-critic",
        "reader-quality-critic",
        "editorial-significance-critic",
        "peer-review-methods-critic",
        "domain-fit-critic",
    ]
    role_reviewers = quorum["reviewers"][3:]
    assert all("review_protocol" in reviewer for reviewer in quorum["reviewers"])
    assert [reviewer["review_protocol"]["lens"] for reviewer in quorum["reviewers"]] == [
        "nature-sci-editor+senior-domain-researcher",
        "parse-materialization-reviewer",
        "source-grounding-reviewer",
        "nature-sci-editor",
        "peer-reviewer",
        "senior-domain-researcher",
    ]
    assert quorum["reviewers"][0]["review_protocol"]["hard_fail_checks"] == [
        "paper_identity",
        "claim_support",
        "benchmark_integrity",
        "scope_overclaim",
    ]
    assert quorum["reviewers"][0]["review_protocol"]["warning_checks"] == [
        "engineering_reproducibility",
        "parse_vs_paper_failure",
    ]
    assert "reader/evidence-map.json" in quorum["reviewers"][2]["review_protocol"]["consumes"]
    assert [reviewer["review_protocol"]["consumes"] for reviewer in role_reviewers] == [
        "reader/editorial-summary.md",
        "reader/technical-reading.md",
        "reader/research-notes.md",
    ]
    assert [reviewer["verdict"] for reviewer in role_reviewers] == ["pass", "pass", "pass"]
    assert report["output_artifact_hashes"]["editorial-significance-critic.md"]
    assert report["output_artifact_hashes"]["peer-review-methods-critic.md"]
    assert report["output_artifact_hashes"]["domain-fit-critic.md"]
    decision = json.loads((paper_root / "critic" / "research-decision.json").read_text(encoding="utf-8"))
    decision_md = (paper_root / "critic" / "research-decision.md").read_text(encoding="utf-8")
    assert decision["schema_version"] == "epi-research-decision-v1"
    assert decision["recommendation"] == "stage-for-promotion-review"
    assert decision["next_action"] == "stage"
    assert decision["decision_inputs"]["final_outcome"] == "pass"
    assert decision["role_verdicts"] == {
        "nature-sci-editor": "pass",
        "peer-reviewer": "pass",
        "senior-domain-researcher": "pass",
    }
    assert [item["lens"] for item in decision["action_items"]] == [
        "nature-sci-editor",
        "peer-reviewer",
        "senior-domain-researcher",
    ]
    assert all(item["action"] == "preserve" for item in decision["action_items"])
    assert decision["panel_summary"] == {
        "consensus": "approve-for-staging",
        "blocking_lenses": [],
        "warning_reviewers": ["paper-quality-critic"],
        "hard_rule": "No critic pass, no compiled wiki write.",
    }
    assert [
        {
            "lens": item["lens"],
            "responsibility": item["responsibility"],
            "artifact": item["artifact"],
            "verdict": item["verdict"],
            "action": item["action"],
            "promotion_blocking": item["promotion_blocking"],
        }
        for item in decision["role_assessments"]
    ] == [
        {
            "lens": "nature-sci-editor",
            "responsibility": "Nature/Sci editorial significance, novelty framing, broad-interest claim discipline",
            "artifact": "reader/editorial-summary.md",
            "verdict": "pass",
            "action": "preserve",
            "promotion_blocking": False,
        },
        {
            "lens": "peer-reviewer",
            "responsibility": "peer-review methods, evidence, benchmark, and reproducibility discipline",
            "artifact": "reader/technical-reading.md",
            "verdict": "pass",
            "action": "preserve",
            "promotion_blocking": False,
        },
        {
            "lens": "senior-domain-researcher",
            "responsibility": "senior researcher fit to the user's configured research profile and agenda",
            "artifact": "reader/research-notes.md",
            "verdict": "pass",
            "action": "preserve",
            "promotion_blocking": False,
        },
    ]
    assert "## Role Verdicts" in decision_md
    assert "## Panel Summary" in decision_md
    assert "## Role Assessment Matrix" in decision_md
    assert "stage-for-promotion-review" in decision_md
    assert report["research_decision_path"] == str(paper_root / "critic" / "research-decision.json")
    assert report["output_artifact_hashes"]["research-decision.json"]
    assert report["output_artifact_hashes"]["research-decision.md"]


def test_peer_review_methods_critic_revises_reader_when_technical_reading_lacks_method_section(tmp_path):
    paper_root = _write_role_critic_fixture(tmp_path)
    generate_reader_outputs(paper_root)
    (paper_root / "reader" / "technical-reading.md").write_text(
        "# Technical Reading\n\n"
        "## Reproducibility Hooks\n"
        "- Code/data/model/config references: fixture, code, dataset.\n"
        "  Evidence: source=metadata.json; field=sources\n",
        encoding="utf-8",
    )

    report = run_critics(paper_root)
    quorum = json.loads((paper_root / "critic" / "critic-quorum.json").read_text(encoding="utf-8"))
    reviewer = next(
        reviewer for reviewer in quorum["reviewers"] if reviewer["name"] == "peer-review-methods-critic"
    )

    assert report["outcome"] == "revise-reader"
    decision = json.loads((paper_root / "critic" / "research-decision.json").read_text(encoding="utf-8"))
    assert reviewer["verdict"] == "fail"
    assert any("missing required section: ## Method Decomposition" in item for item in reviewer["evidence"])
    assert decision["recommendation"] == "revise-reader"
    assert decision["next_action"] == "revise-reader"
    assert decision["role_verdicts"]["peer-reviewer"] == "fail"
    assert decision["panel_summary"]["consensus"] == "revise-before-staging"
    assert decision["panel_summary"]["blocking_lenses"] == ["peer-reviewer"]
    peer_assessment = next(item for item in decision["role_assessments"] if item["lens"] == "peer-reviewer")
    assert peer_assessment["artifact"] == "reader/technical-reading.md"
    assert peer_assessment["promotion_blocking"] is True
    assert peer_assessment["required_sections"] == [
        "## Method Decomposition",
        "## Reproducibility Hooks",
        "## Reviewer Checkpoint",
    ]
    assert any(
        item["lens"] == "peer-reviewer"
        and item["action"] == "revise"
        and "## Method Decomposition" in item["evidence"][0]
        for item in decision["action_items"]
    )
