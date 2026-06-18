import json
from datetime import date

from paper_source.discovery_benchmark import run_discovery_benchmark
from paper_source.evaluation_loop import validate_benchmark_contract


def _write_benchmark_case(tmp_path):
    current_year = date.today().year
    case_path = tmp_path / "discovery-benchmark-cases.json"
    payload = {
        "schema_version": "paper-source-discovery-benchmark-cases-v1",
        "benchmark_id": "paper-source-discovery-fixture",
        "cases": [
            {
                "id": "auv-rl-control-non-review",
                "query": "Find latest high-quality AUV reinforcement learning control papers, not reviews",
                "profile": {
                    "name": "marine_robotics",
                    "domains": ["AUV", "control"],
                    "positive_keywords": ["ocean current", "sim-to-real"],
                    "negative_keywords": ["game-only"],
                    "venue_prior": ["Ocean Engineering"],
                },
                "raw_records": [
                    {
                        "source": "openalex",
                        "provider": "paper_search",
                        "title": "Recent AUV Reinforcement Learning Control with Field Trials",
                        "authors": ["A. Researcher"],
                        "year": current_year,
                        "venue": "Ocean Engineering",
                        "abstract": (
                            "AUV reinforcement learning control under ocean current with sim-to-real "
                            "field trials, benchmark baselines, ablation experiments, and open code."
                        ),
                        "doi": "10.1000/recent-auv",
                        "pdf_url": "https://example.org/recent.pdf",
                        "code_url": "https://github.com/example/recent-auv",
                        "citation_count": 24,
                    },
                    {
                        "source": "crossref",
                        "provider": "paper_search",
                        "title": "Recent AUV Reinforcement Learning Control with Field Trials",
                        "authors": ["A. Researcher"],
                        "year": current_year,
                        "venue": "Ocean Engineering",
                        "abstract": "Duplicate metadata record for the same AUV control paper.",
                        "doi": "10.1000/recent-auv",
                        "pdf_url": "https://example.org/recent.pdf",
                        "citation_count": 24,
                    },
                    {
                        "source": "openalex",
                        "provider": "paper_search",
                        "title": "Highly Cited AUV Reinforcement Learning Control Baseline",
                        "authors": ["B. Researcher"],
                        "year": current_year - 8,
                        "venue": "IEEE Transactions on Control Systems Technology",
                        "abstract": "AUV reinforcement learning control benchmark with simulation evidence.",
                        "doi": "10.1000/old-auv",
                        "pdf_url": "https://example.org/old.pdf",
                        "citation_count": 260,
                    },
                    {
                        "source": "semantic",
                        "provider": "paper_search",
                        "title": "Survey of AUV Reinforcement Learning Control",
                        "authors": ["C. Researcher"],
                        "year": current_year,
                        "venue": "Robotics Surveys",
                        "abstract": "A survey review of AUV reinforcement learning control papers.",
                        "doi": "10.1000/survey-auv",
                        "pdf_url": "https://example.org/survey.pdf",
                        "citation_count": 99,
                    },
                    {
                        "source": "semantic",
                        "provider": "paper_search",
                        "title": "AUV RL Control Conference Note",
                        "authors": ["D. Researcher"],
                        "year": current_year,
                        "venue": "Marine Robotics Workshop",
                        "abstract": "AUV reinforcement learning control note with ocean current experiments.",
                        "doi": "10.1000/conference-auv",
                        "pdf_url": "https://example.org/conference.pdf",
                        "citation_count": 4,
                        "official_version": {
                            "source": "crossref",
                            "provider": "paper_search",
                            "title": "Journal Version of AUV RL Control with Ocean Current Field Evidence",
                            "authors": ["D. Researcher"],
                            "year": current_year,
                            "venue": "Ocean Engineering",
                            "abstract": (
                                "Journal version of AUV reinforcement learning control with ocean current "
                                "field evidence, benchmark comparison, and open code."
                            ),
                            "doi": "10.1000/journal-auv",
                            "pdf_url": "https://example.org/journal.pdf",
                            "code_url": "https://github.com/example/journal-auv",
                            "citation_count": 31,
                        },
                    },
                ],
                "expectations": {
                    "relevant_titles": [
                        "Recent AUV Reinforcement Learning Control with Field Trials",
                        "Highly Cited AUV Reinforcement Learning Control Baseline",
                        "AUV RL Control Conference Note",
                        "Journal Version of AUV RL Control with Ocean Current Field Evidence",
                    ],
                    "required_recall_titles": [
                        "Journal Version of AUV RL Control with Ocean Current Field Evidence"
                    ],
                    "required_query_plan_terms": ["ocean current", "sim-to-real"],
                    "min_precision_at_10": 0.75,
                    "max_review_leakage": 0,
                    "max_duplicate_rate": 0.25,
                    "min_verified_metric_coverage": 0.75,
                    "citation_normalization": {
                        "preferred_title": "Recent AUV Reinforcement Learning Control with Field Trials",
                        "comparison_title": "Highly Cited AUV Reinforcement Learning Control Baseline",
                        "preserve_absolute_citation_count": {
                            "title": "Highly Cited AUV Reinforcement Learning Control Baseline",
                            "citation_count": 260,
                        },
                    },
                },
            }
        ],
    }
    case_path.write_text(json.dumps(payload), encoding="utf-8")
    return case_path


def test_discovery_benchmark_runs_local_fixture_and_writes_contract(tmp_path):
    case_path = _write_benchmark_case(tmp_path)
    output_path = tmp_path / "benchmark.json"

    benchmark = run_discovery_benchmark(case_path, output_path=output_path)

    assert benchmark["schema_version"] == "paper-source-benchmark-v1"
    assert benchmark["status"] == "pass"
    assert benchmark["output_path"] == str(output_path)
    assert validate_benchmark_contract(benchmark)["valid"] is True
    case = benchmark["cases"][0]
    assert case["raw_candidate_count"] == 5
    assert case["deduped_candidate_count"] == 4
    assert case["accepted_count"] == 4
    assert case["rejected_count"] == 1
    assert case["review_leakage"] == 0
    assert case["recall_gaps"]["recovered"] == 1
    assert case["metrics"]["duplicate_rate"] == 0.2
    assert case["metrics"]["verified_metric_coverage"] >= 0.75
    assert {check["id"]: check["passed"] for check in case["checks"]} == {
        "precision_at_10": True,
        "review_leakage": True,
        "duplicate_rate": True,
        "verified_metric_coverage": True,
        "recall_at_20": True,
        "config_terms_in_query_plan": True,
        "normalized_citation_order": True,
        "absolute_citation_count_preserved": True,
    }
    assert output_path.exists()
