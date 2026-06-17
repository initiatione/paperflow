import json

from paper_source.grok_search_adapter import _configured_model_fallbacks, discover_grok, normalize_grok_payload


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


def test_discover_grok_uses_supported_detailed_response_format(tmp_path, monkeypatch):
    captured = {}

    def fake_call(tool_name, arguments, timeout_seconds, **kwargs):
        captured["tool_name"] = tool_name
        captured["arguments"] = arguments
        captured["env_overrides"] = kwargs.get("env_overrides")
        return {
            "payload": {
                "sources": [
                    {
                        "title": "AUV Attitude Control",
                        "url": "https://doi.org/10.1000/auv-attitude",
                        "content": "Underwater robot attitude tracking paper.",
                    }
                ]
            },
            "raw_response": {"ok": True},
        }

    monkeypatch.delenv("OPENAI_COMPATIBLE_MODEL", raising=False)
    monkeypatch.delenv("PAPER_SOURCE_GROK_MODEL_FALLBACKS", raising=False)
    monkeypatch.setenv("PAPER_SOURCE_GROK_SEARCH_MCP_COMMAND", "configured-grok")
    monkeypatch.setattr("paper_source.grok_search_adapter._mcp_command_args", lambda: (["configured-grok"], {}))
    monkeypatch.setattr("paper_source.grok_search_adapter._call_mcp_tool", fake_call)

    record = discover_grok(
        queries=["AUV attitude control"],
        include_domains=["ieeexplore.ieee.org"],
        raw_response_path=tmp_path / "raw.json",
        evidence_path=tmp_path / "evidence.json",
    )

    assert record["status"] == "ok"
    assert captured["tool_name"] == "web_search"
    assert captured["arguments"]["response_format"] == "detailed"
    assert captured["env_overrides"]["OPENAI_COMPATIBLE_MODEL"] == "grok-4.20-multi-agent-xhigh"


def test_configured_model_fallbacks_preserve_primary_before_defaults(monkeypatch):
    monkeypatch.setenv("OPENAI_COMPATIBLE_MODEL", "custom-primary")
    monkeypatch.setenv(
        "PAPER_SOURCE_GROK_MODEL_FALLBACKS",
        "custom-primary,grok-4.20-multi-agent-high grok-4.20-multi-agent-medium",
    )

    assert _configured_model_fallbacks()[:4] == [
        "custom-primary",
        "grok-4.20-multi-agent-high",
        "grok-4.20-multi-agent-medium",
        "grok-4.20-multi-agent-xhigh",
    ]


def test_discover_grok_retries_retryable_provider_fallback_with_next_model(tmp_path, monkeypatch):
    attempts = []

    def fake_call(tool_name, arguments, timeout_seconds, **kwargs):
        model = kwargs["env_overrides"]["OPENAI_COMPATIBLE_MODEL"]
        attempts.append(model)
        if model == "primary-model":
            return {
                "payload": {
                    "fallback_used": True,
                    "fallback_reason": "grok_provider_error",
                    "search_provider": "source_fallback",
                    "sources": [],
                    "sources_count": 0,
                },
                "raw_response": {"model": model},
            }
        return {
            "payload": {
                "fallback_used": False,
                "fallback_reason": None,
                "search_provider": "grok_responses",
                "sources": [
                    {
                        "title": "AUV Control Paper",
                        "url": "https://doi.org/10.1000/auv-control",
                        "content": "Underwater robot control paper.",
                    }
                ],
                "sources_count": 1,
            },
            "raw_response": {"model": model},
        }

    monkeypatch.setenv("OPENAI_COMPATIBLE_MODEL", "primary-model")
    monkeypatch.setenv("PAPER_SOURCE_GROK_MODEL_FALLBACKS", "backup-model")
    monkeypatch.setenv("PAPER_SOURCE_GROK_SEARCH_MCP_COMMAND", "configured-grok")
    monkeypatch.setattr("paper_source.grok_search_adapter._mcp_command_args", lambda: (["configured-grok"], {}))
    monkeypatch.setattr("paper_source.grok_search_adapter._call_mcp_tool", fake_call)

    record = discover_grok(
        queries=["AUV control"],
        include_domains=[],
        raw_response_path=tmp_path / "raw.json",
        evidence_path=tmp_path / "evidence.json",
    )

    raw = json.loads((tmp_path / "raw.json").read_text(encoding="utf-8"))
    model_attempts = raw["responses"][0]["model_attempts"]
    assert attempts == ["primary-model", "backup-model"]
    assert record["status"] == "ok"
    assert record["records"][0]["doi"] == "10.1000/auv-control"
    assert model_attempts == [
        {
            "model": "primary-model",
            "status": "retryable_fallback",
            "search_provider": "source_fallback",
            "fallback_used": True,
            "fallback_reason": "grok_provider_error",
            "sources_count": 0,
        },
        {
            "model": "backup-model",
            "status": "ok",
            "search_provider": "grok_responses",
            "fallback_used": False,
            "fallback_reason": None,
            "sources_count": 1,
        },
    ]


def test_discover_grok_retries_source_fallback_without_fallback_flag(tmp_path, monkeypatch):
    attempts = []

    def fake_call(tool_name, arguments, timeout_seconds, **kwargs):
        model = kwargs["env_overrides"]["OPENAI_COMPATIBLE_MODEL"]
        attempts.append(model)
        if model == "primary-model":
            return {
                "payload": {
                    "fallback_used": False,
                    "search_provider": "source_fallback",
                    "sources": [],
                    "sources_count": 0,
                },
                "raw_response": {"model": model},
            }
        return {
            "payload": {
                "search_provider": "grok_responses",
                "sources": [
                    {
                        "title": "AUV Control Paper",
                        "url": "https://doi.org/10.1000/auv-control",
                        "content": "Underwater robot control paper.",
                    }
                ],
                "sources_count": 1,
            },
            "raw_response": {"model": model},
        }

    monkeypatch.setenv("OPENAI_COMPATIBLE_MODEL", "primary-model")
    monkeypatch.setenv("PAPER_SOURCE_GROK_MODEL_FALLBACKS", "backup-model")
    monkeypatch.setenv("PAPER_SOURCE_GROK_SEARCH_MCP_COMMAND", "configured-grok")
    monkeypatch.setattr("paper_source.grok_search_adapter._mcp_command_args", lambda: (["configured-grok"], {}))
    monkeypatch.setattr("paper_source.grok_search_adapter._call_mcp_tool", fake_call)

    record = discover_grok(
        queries=["AUV control"],
        include_domains=[],
        raw_response_path=tmp_path / "raw.json",
        evidence_path=tmp_path / "evidence.json",
    )

    assert attempts == ["primary-model", "backup-model"]
    assert record["status"] == "ok"
