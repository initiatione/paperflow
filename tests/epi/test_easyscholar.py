import json
import urllib.parse

from epi.easyscholar import (
    EasyScholarConfig,
    cache_key_for_publication,
    enrich_candidates_with_easyscholar,
    normalize_publication_name,
    parse_easyscholar_response,
    publication_name_for_candidate,
    score_easyscholar_metrics,
)


def _successful_response() -> dict:
    return {
        "code": 200,
        "msg": "success",
        "data": {
            "officialRank": {
                "select": {
                    "sci": "Q1",
                    "sciBase": "1",
                    "sciUp": "1",
                    "sciUpTop": "TOP",
                    "sciif5": "11.2",
                },
                "all": {
                    "sciif": "9.4",
                    "jci": "1.8",
                    "esi": "Engineering",
                    "eii": "Yes",
                    "ccf": "A",
                    "ccfConference": "A",
                    "abdc": "A*",
                    "ajg": "4*",
                    "ft50": "Yes",
                    "utd24": "Yes",
                    "pku": "Yes",
                    "cssci": "Yes",
                    "cscd": "Yes",
                },
            }
        },
    }


def test_parse_easyscholar_response_extracts_supported_metrics():
    parsed = parse_easyscholar_response("Journal of Applied Psychology", _successful_response())

    assert parsed["status"] == "matched"
    assert parsed["publication_name"] == "Journal of Applied Psychology"
    assert parsed["source"] == "easyscholar"
    assert parsed["metrics"] == {
        "jcr_quartile": "Q1",
        "cas_zone_basic": "1",
        "cas_zone_upgraded": "1",
        "cas_top": "TOP",
        "impact_factor": "9.4",
        "five_year_impact_factor": "11.2",
        "jci": "1.8",
        "esi_subject": "Engineering",
        "ei": "Yes",
        "ccf": "A",
        "ccf_conference": "A",
        "abdc": "A*",
        "ajg": "4*",
        "ft50": "Yes",
        "utd24": "Yes",
        "pku_core": "Yes",
        "cssci": "Yes",
        "cscd": "Yes",
    }
    assert parsed["warnings"] == []


def test_parse_easyscholar_response_marks_no_match_when_no_rank_data():
    parsed = parse_easyscholar_response(
        "Unknown Venue",
        {"code": 200, "data": {"officialRank": {"select": {}, "all": {}}}},
    )

    assert parsed["status"] == "no_match"
    assert parsed["metrics"] == {}
    assert "no_ranking_data" in parsed["warnings"]


def test_score_easyscholar_metrics_maps_strong_and_warning_signals():
    parsed = parse_easyscholar_response("Journal of Applied Psychology", _successful_response())
    signal = score_easyscholar_metrics(parsed["metrics"])

    assert signal["score"] == 1.0
    assert "JCR Q1" in signal["evidence"]
    assert "CAS 1" in signal["evidence"]
    assert "CCF A" in signal["evidence"]
    assert "ABDC A*" in signal["evidence"]
    assert "AJG 4*" in signal["evidence"]
    assert "impact_factor:9.4" in signal["evidence"]
    assert signal["cautions"] == []

    warning_signal = score_easyscholar_metrics({"jcr_quartile": "Q4", "cas_warning": "warning"})

    assert warning_signal["score"] < 0.3
    assert "cas_warning" in warning_signal["cautions"]


def test_publication_name_falls_back_to_raw_record_fields():
    candidate = {
        "venue": "",
        "raw_records": [
            {"extra": {"publication_venue": "IEEE Robotics and Automation Letters"}},
            {"journal": "Ignored Journal"},
        ],
    }

    assert publication_name_for_candidate(candidate) == "IEEE Robotics and Automation Letters"


def test_normalize_publication_name_and_cache_key_are_stable():
    assert normalize_publication_name(" Journal  of Applied Psychology! ") == "journal of applied psychology"

    first = cache_key_for_publication("Journal of Applied Psychology")
    second = cache_key_for_publication(" journal  of applied psychology ")

    assert first == second
    assert first.endswith(".json")
    assert "/" not in first


def test_enrich_candidates_soft_fails_when_secret_key_missing(tmp_path):
    candidates = [
        {
            "title": "Fixture Paper",
            "venue": "Journal of Applied Psychology",
            "abstract": "control benchmark",
        }
    ]

    enriched, record = enrich_candidates_with_easyscholar(
        candidates,
        EasyScholarConfig(vault_path=tmp_path, secret_key=None),
    )

    assert enriched[0]["easyscholar_status"] == "missing_key"
    assert enriched[0]["verified_metrics"]["easyscholar"]["status"] == "missing_key"
    assert enriched[0]["quality_signals"]["easyscholar"]["score"] == 0.0
    assert record["summary"]["missing_key"] == 1
    assert record["summary"]["matched"] == 0
    assert record["summary"]["timeout"] == 0
    assert "secret" not in json.dumps(record).lower()


def test_enrich_candidates_uses_cache_without_calling_client(tmp_path):
    cache_root = tmp_path / "_epi" / "cache" / "easyscholar"
    cache_root.mkdir(parents=True)
    cache_path = cache_root / cache_key_for_publication("Journal of Applied Psychology")
    cache_path.write_text(
        json.dumps(
            {
                "schema_version": "epi-easyscholar-cache-v1",
                "publication_name": "Journal of Applied Psychology",
                "normalized_publication_name": "journal of applied psychology",
                "queried_at": "2026-06-04T00:00:00+00:00",
                "expires_at": "2999-01-01T00:00:00+00:00",
                "status": "matched",
                "raw_response": _successful_response(),
                "parsed_metrics": parse_easyscholar_response(
                    "Journal of Applied Psychology",
                    _successful_response(),
                ),
                "error": None,
            }
        ),
        encoding="utf-8",
    )

    def client(publication_name, secret_key, timeout_seconds):
        raise AssertionError("cache hit should not call EasyScholar")

    enriched, record = enrich_candidates_with_easyscholar(
        [{"title": "Fixture Paper", "venue": "Journal of Applied Psychology"}],
        EasyScholarConfig(vault_path=tmp_path, secret_key="dummy-secret", client=client),
    )

    assert enriched[0]["easyscholar_status"] == "cache_hit"
    assert enriched[0]["verified_metrics"]["easyscholar"]["status"] == "matched"
    assert enriched[0]["quality_signals"]["easyscholar"]["score"] == 1.0
    assert record["summary"]["cache_hit"] == 1
    assert "dummy-secret" not in json.dumps(record)


def test_enrich_candidates_records_api_error_without_secret(tmp_path):
    secret_key = "dummy secret/value"
    encoded_secret = urllib.parse.quote_plus(secret_key)

    def client(publication_name, secret_key, timeout_seconds):
        raise RuntimeError(
            "upstream failed with "
            f"{secret_key} and https://www.easyscholar.cc/open/getPublicationRank?secretKey={encoded_secret}"
        )

    enriched, record = enrich_candidates_with_easyscholar(
        [{"title": "Fixture Paper", "venue": "Journal of Applied Psychology"}],
        EasyScholarConfig(vault_path=tmp_path, secret_key=secret_key, client=client),
    )

    assert enriched[0]["easyscholar_status"] == "api_error"
    assert enriched[0]["quality_signals"]["easyscholar"]["score"] == 0.0
    assert record["summary"]["api_error"] == 1
    serialized = json.dumps(record)
    assert secret_key not in serialized
    assert encoded_secret not in serialized
    assert "upstream failed" in serialized
