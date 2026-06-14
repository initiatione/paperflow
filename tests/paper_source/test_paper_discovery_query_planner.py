import json
import subprocess
import sys
from pathlib import Path

from paper_source.query_planner import build_query_plan


ROOT = Path(__file__).resolve().parents[2]
PLANNER = ROOT / "plugins" / "paper-source" / "skills" / "paper-discovery" / "scripts" / "query-planner.py"


def test_query_planner_generates_profile_derived_non_review_plan():
    result = subprocess.run(
        [
            sys.executable,
            str(PLANNER),
            "--topic",
            "latest high quality graph neural network molecular property prediction papers",
            "--profile",
            "computational_chemistry",
            "--domains",
            "computational chemistry,molecular property prediction",
            "--positive-keywords",
            "graph neural network,quantum chemistry benchmark",
            "--venue-prior",
            "JACS,Journal of Chemical Information and Modeling",
            "--non-review",
            "--max-queries",
            "8",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    plan = json.loads(result.stdout)

    assert plan["workflow"] == "paper-source-query-plan"
    assert plan["research_mode"]["schema_version"] == "paper-source-research-mode-v1"
    assert plan["research_mode"]["mode"] == "targeted-discovery"
    assert plan["domain"] == "profile-derived"
    assert plan["profile"]["name"] == "computational_chemistry"
    assert "computational chemistry" in plan["concept_blocks"]["domain_terms"]
    assert "graph neural network" in plan["concept_blocks"]["method_or_topic_terms"]
    assert "molecular property prediction" in plan["concept_blocks"]["profile_terms"]
    assert "benchmark" in plan["concept_blocks"]["quality_signals"]
    assert "review" in plan["concept_blocks"]["exclusions"]
    assert len(plan["query_variants"]) >= 5
    assert all("-review -survey" in query for query in plan["query_variants"])
    assert "paper_search_mcp" in plan["source_route"]["t1"]
    assert "unpaywall" in plan["source_route"]["t1"]
    assert "JACS" in plan["recall_gap_checks"]["venue_families"]
    assert "recent cited-by" in plan["recall_gap_checks"]["citation_graph"]


def test_query_planner_defaults_to_non_review_for_discovery_topics():
    result = subprocess.run(
        [
            sys.executable,
            str(PLANNER),
            "--topic",
            "latest high quality molecular property prediction papers",
            "--profile",
            "computational_chemistry",
            "--domains",
            "computational chemistry",
            "--max-queries",
            "4",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    plan = json.loads(result.stdout)

    assert all("-review -survey" in query for query in plan["query_variants"])
    assert plan["research_mode"]["mode"] == "targeted-discovery"


def test_query_planner_can_keep_reviews_when_explicitly_requested():
    result = subprocess.run(
        [
            sys.executable,
            str(PLANNER),
            "--topic",
            "latest survey papers about molecular property prediction",
            "--profile",
            "computational_chemistry",
            "--domains",
            "computational chemistry",
            "--include-reviews",
            "--max-queries",
            "4",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    plan = json.loads(result.stdout)

    assert all("-review -survey" not in query for query in plan["query_variants"])
    assert plan["research_mode"]["mode"] == "lit-review"


def test_query_planner_detects_systematic_review_mode_without_non_review_block():
    plan = build_query_plan(
        "systematic review with PRISMA about molecular property prediction",
        non_review=None,
        max_queries=4,
    )

    assert plan["research_mode"]["mode"] == "systematic-review"
    assert plan["research_mode"]["spectrum"] == "fidelity"
    assert all("-review -survey" not in query for query in plan["query_variants"])


def test_query_planner_does_not_route_not_review_queries_to_lit_review_mode():
    plan = build_query_plan(
        "latest high quality robot control papers not review",
        non_review=True,
        max_queries=4,
    )

    assert plan["research_mode"]["mode"] == "targeted-discovery"


def test_query_planner_does_not_auto_detect_fixed_discipline_domains():
    result = subprocess.run(
        [
            sys.executable,
            str(PLANNER),
            "--topic",
            "embodied AI world model robot learning manipulation papers",
            "--domain",
            "auto",
            "--max-queries",
            "6",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    plan = json.loads(result.stdout)

    assert plan["domain"] == "topic-derived"
    assert "world model" in plan["concept_blocks"]["method_or_topic_terms"]
    joined_venues = " ".join(plan["recall_gap_checks"]["venue_families"]).lower()
    assert "corl" not in joined_venues
    assert "icra" not in joined_venues


def test_query_planner_rejects_fixed_discipline_domain_packs():
    try:
        build_query_plan(
            "latest high quality AUV reinforcement learning control papers",
            domain="auv-control",
            non_review=True,
            max_queries=4,
        )
    except ValueError as exc:
        assert "unknown domain: auv-control" in str(exc)
    else:
        raise AssertionError("fixed discipline domain packs should not be accepted")


def test_query_planner_promotes_explicit_topic_domain_over_broad_profile_terms():
    plan = build_query_plan(
        "latest high quality AUV reinforcement learning control papers not review",
        domain="auto",
        non_review=True,
        max_queries=6,
        profile="robotics_ai_control",
        domains=[
            "robotics",
            "robot control",
            "embodied intelligence",
            "artificial intelligence",
            "reinforcement learning",
            "AUV control",
        ],
        positive_keywords=[
            "robot control",
            "reinforcement learning",
            "learning-based control",
            "AUV",
            "underwater robot",
        ],
    )

    assert plan["domain"] == "profile-derived"
    assert "AUV control" in plan["concept_blocks"]["domain_focus_terms"]
    assert "reinforcement learning" not in plan["concept_blocks"]["domain_focus_terms"]
    assert "autonomous underwater vehicle" not in plan["concept_blocks"]["domain_terms"]
    assert "Ocean Engineering" not in plan["recall_gap_checks"]["venue_families"]
    assert any("AUV" in query or "underwater" in query for query in plan["query_variants"][:3])
    assert not any(
        query.startswith('robotics "robot control"')
        for query in plan["query_variants"][:3]
    )


def test_query_planner_keeps_generated_queries_academic_without_domain_specific_nlp_rules():
    topic = "recent high quality energy storage control papers with open code from the last five years"

    plan = build_query_plan(
        topic,
        domain="auto",
        non_review=True,
        max_queries=6,
        profile="energy_systems_control",
        domains=["energy systems", "battery energy storage"],
        positive_keywords=["model predictive control", "reproducible code"],
    )

    queries = plan["query_variants"]

    assert plan["domain"] == "profile-derived"
    assert topic not in queries
    assert all("recent high quality" not in query.lower() for query in queries)
    assert all("last five years" not in query.lower() for query in queries)
    assert all("-review -survey" in query for query in queries)
    assert any("energy storage" in query.lower() for query in queries)


def test_query_planner_derives_generic_topic_anchors_from_narrow_request():
    plan = build_query_plan(
        "latest high quality graph neural network molecular property prediction papers not review",
        domain="auto",
        non_review=True,
        max_queries=5,
        profile="machine_learning_research",
        domains=["machine learning", "artificial intelligence"],
        positive_keywords=["graph neural network", "deep learning"],
    )

    assert plan["domain"] == "profile-derived"
    assert "molecular property prediction" in plan["concept_blocks"]["domain_focus_terms"]
    assert "graph neural network" not in plan["concept_blocks"]["domain_focus_terms"]
    assert plan["concept_blocks"]["domain_terms"][0] == "molecular property prediction"


def test_query_planner_keeps_non_robotics_profile_free_of_robotics_defaults():
    plan = build_query_plan(
        "latest high quality single cell RNA sequencing biomarker discovery papers not review",
        domain="auto",
        non_review=True,
        max_queries=6,
        profile="biomedical_genomics",
        domains=["biomedical genomics", "single cell RNA sequencing", "biomarker discovery"],
        positive_keywords=["spatial transcriptomics", "clinical validation"],
        venue_prior=["Nature Genetics", "Genome Biology", "Cell Genomics"],
    )

    joined_blocks = json.dumps(plan["concept_blocks"], ensure_ascii=False).lower()
    joined_venues = " ".join(plan["recall_gap_checks"]["venue_families"]).lower()
    joined_queries = " ".join(plan["query_variants"]).lower()

    assert plan["domain"] == "profile-derived"
    assert "single cell RNA sequencing" in plan["concept_blocks"]["domain_focus_terms"]
    assert "biomarker discovery" in plan["concept_blocks"]["domain_focus_terms"]
    assert "clinical validation" in plan["concept_blocks"]["method_or_topic_terms"]
    assert "nature genetics" in joined_venues
    assert "robot" not in joined_blocks
    assert "auv" not in joined_blocks
    assert "icra" not in joined_venues
    assert "single cell" in joined_queries
    assert all("-review -survey" in query for query in plan["query_variants"])


def test_query_planner_module_matches_skill_wrapper_shape():
    plan = build_query_plan(
        "latest high quality graph neural network molecular property prediction papers",
        profile="computational_chemistry",
        domains=["computational chemistry"],
        positive_keywords=["graph neural network"],
        non_review=True,
        max_queries=4,
    )

    assert plan["workflow"] == "paper-source-query-plan"
    assert plan["domain"] == "profile-derived"
    assert len(plan["query_variants"]) == 4
    assert all("-review -survey" in query for query in plan["query_variants"])
