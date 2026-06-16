from paper_source.config import GrokAcademicDomainsConfig, GrokSearchConfig
from paper_source.grok_search_policy import (
    build_parallel_grok_queries,
    build_targeted_grok_queries,
    grok_only_quota,
    paper_search_good_enough,
    resolve_grok_mode,
    usable_paper_search_candidate,
)


def _config(mode="targeted"):
    return GrokSearchConfig(
        mode=mode,
        targeted_query_budget=5,
        parallel_query_budget=8,
        grok_only_recommendation_cap=5,
        academic_domains=GrokAcademicDomainsConfig(mode="append", domains=[], effective_domains=[]),
    )


def _ranked(title, *, tier="Tier A", decision="advance-candidate", doi="10.1000/example", provider="paper_search"):
    return {
        "title": title,
        "doi": doi,
        "quality_tier": tier,
        "staging_readiness": "staging_ready",
        "ranking_protocol": {"decision": decision},
        "provider_provenance": [provider],
    }


def test_resolve_grok_mode_silently_turns_off_when_runtime_missing():
    mode = resolve_grok_mode(_config("targeted"), runtime_configured=False)

    assert mode.mode == "off"
    assert mode.requested_mode == "targeted"
    assert mode.reason == "not_configured"


def test_resolve_grok_mode_honors_cli_disable():
    mode = resolve_grok_mode(_config("parallel"), cli_mode="targeted", no_grok_search=True, runtime_configured=True)

    assert mode.mode == "off"
    assert mode.reason == "disabled_by_cli"


def test_paper_search_good_enough_requires_quality_identity_and_no_provider_gap():
    ranked = [_ranked("A"), _ranked("B", tier="Tier B"), _ranked("C", decision="review-candidate")]

    assert paper_search_good_enough(ranked, source_routing={"provider_gaps": []}) is True
    assert (
        paper_search_good_enough(
            ranked,
            source_routing={"provider_gaps": [{"provider": "unpaywall", "importance": "required"}]},
        )
        is False
    )


def test_targeted_queries_prioritize_provider_gaps_before_broad_recall():
    queries = build_targeted_grok_queries(
        query="AUV reinforcement learning control",
        query_plan={"query_variants": ["AUV RL control", "underwater robot reinforcement learning"]},
        source_routing={"provider_gaps": [{"provider": "unpaywall", "importance": "required"}]},
        ranked=[],
        budget=3,
    )

    assert queries[0].startswith("AUV reinforcement learning control unpaywall")
    assert len(queries) == 3


def test_parallel_queries_cover_query_variants_then_gap_domains():
    queries = build_parallel_grok_queries(
        query="robotics control",
        query_plan={"query_variants": ["robotics MPC", "robotics RL"]},
        source_routing={"demoted_sources": [{"source": "google_scholar"}]},
        budget=5,
    )

    assert queries[0].startswith("robotics MPC")
    assert queries[1].startswith("robotics RL")
    assert any("google_scholar" in query for query in queries)
    assert len(queries) == 5


def test_grok_only_quota_requires_paper_search_anchor_and_hard_cap():
    ranked = [_ranked("A"), _ranked("B"), _ranked("Grok", provider="grok_search")]

    assert usable_paper_search_candidate(ranked[0]) is True
    assert usable_paper_search_candidate(ranked[2]) is False
    assert grok_only_quota(ranked, cap=5) == 2
    assert grok_only_quota(ranked, cap=1) == 1
