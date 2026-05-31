import json
import subprocess
import sys
from pathlib import Path

from epi.query_planner import build_query_plan


ROOT = Path(__file__).resolve().parents[2]
PLANNER = ROOT / "plugins" / "epi" / "skills" / "paper-discovery" / "scripts" / "query-planner.py"


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

    assert plan["workflow"] == "epi-query-plan"
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


def test_query_planner_auto_detects_embodied_ai_domain():
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

    assert plan["domain"] == "embodied-ai"
    assert "world model" in plan["concept_blocks"]["method_or_topic_terms"]
    assert "CoRL" in plan["recall_gap_checks"]["venue_families"]


def test_query_planner_keeps_explicit_domain_hint_as_optional_pack():
    plan = build_query_plan(
        "latest high quality AUV reinforcement learning control papers",
        domain="auv-control",
        non_review=True,
        max_queries=4,
    )

    assert plan["domain"] == "auv-control"
    assert "autonomous underwater vehicle" in plan["concept_blocks"]["domain_terms"]
    assert "Ocean Engineering" in plan["recall_gap_checks"]["venue_families"]


def test_query_planner_module_matches_skill_wrapper_shape():
    plan = build_query_plan(
        "latest high quality graph neural network molecular property prediction papers",
        profile="computational_chemistry",
        domains=["computational chemistry"],
        positive_keywords=["graph neural network"],
        non_review=True,
        max_queries=4,
    )

    assert plan["workflow"] == "epi-query-plan"
    assert plan["domain"] == "profile-derived"
    assert len(plan["query_variants"]) == 4
    assert all("-review -survey" in query for query in plan["query_variants"])
