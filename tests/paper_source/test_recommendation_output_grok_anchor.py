from paper_source.recommendation_output import build_session_recommendations


def _candidate(title, provider, *, doi="10.1000/example"):
    return {
        "slug": title.lower().replace(" ", "-"),
        "title": title,
        "quality_tier": "Tier A",
        "staging_readiness": "staging_ready",
        "ranking_protocol": {"decision": "advance-candidate"},
        "provider_provenance": [provider],
        "provenance_label": "paper_search_only"
        if provider == "paper_search"
        else "grok_only_with_paper_search_anchor",
        "doi": doi,
    }


def test_recommendations_do_not_surface_grok_only_without_paper_search_anchor():
    ranked = [_candidate("Grok Only", "grok_search")]

    session = build_session_recommendations(ranked, [])

    assert session["primary_recommendations"] == []


def test_recommendations_allow_capped_grok_only_with_paper_search_anchor():
    ranked = [
        _candidate("Paper Search One", "paper_search", doi="10.1000/p1"),
        _candidate("Paper Search Two", "paper_search", doi="10.1000/p2"),
        _candidate("Grok One", "grok_search", doi="10.1000/g1"),
        _candidate("Grok Two", "grok_search", doi="10.1000/g2"),
        _candidate("Grok Three", "grok_search", doi="10.1000/g3"),
    ]

    session = build_session_recommendations(ranked, [])

    titles = [item["title"] for item in session["primary_recommendations"]]
    assert titles == ["Paper Search One", "Paper Search Two", "Grok One", "Grok Two"]
    assert session["primary_recommendations"][2]["provenance_label"] == "grok_only_with_paper_search_anchor"
