from paper_source.grok_search_adapter import normalize_grok_payload


def test_normalize_grok_payload_accepts_stable_paper_identity():
    payload = {
        "sources": [
            {
                "title": "Learning AUV Control",
                "url": "https://doi.org/10.1000/auv-control",
                "content": "A paper about underwater vehicle control.",
                "authors": ["A. Researcher"],
                "year": 2025,
            },
            {
                "title": "Project page",
                "url": "https://example.org/project",
                "content": "A blog page with no stable paper identity.",
            },
        ]
    }

    accepted, evidence = normalize_grok_payload(payload, query="AUV control", index=1)

    assert len(accepted) == 1
    assert accepted[0]["provider"] == "grok_search"
    assert accepted[0]["doi"] == "10.1000/auv-control"
    assert accepted[0]["landing_page_url"] == "https://doi.org/10.1000/auv-control"
    assert evidence == [
        {
            "provider": "grok_search",
            "query": "AUV control",
            "title": "Project page",
            "url": "https://example.org/project",
            "reason": "missing_stable_paper_identity",
            "raw_record": payload["sources"][1],
        }
    ]


def test_normalize_grok_payload_accepts_arxiv_pdf_without_doi():
    payload = {
        "sources": [
            {
                "title": "Robot Learning",
                "url": "https://arxiv.org/pdf/2501.12345",
                "content": "arXiv:2501.12345",
            }
        ]
    }

    accepted, evidence = normalize_grok_payload(payload, query="robot learning", index=2)

    assert evidence == []
    assert accepted[0]["arxiv_id"] == "2501.12345"
    assert accepted[0]["pdf_url"] == "https://arxiv.org/pdf/2501.12345"
