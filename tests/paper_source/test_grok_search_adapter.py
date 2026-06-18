import json

from paper_source import grok_search_adapter as adapter
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
            "quality_state": "evidence_only",
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


def test_call_mcp_tool_waits_after_kill_on_terminate_timeout(monkeypatch):
    events = []

    class _FakeStdin:
        def close(self):
            events.append("stdin.close")

    class _FakeProcess:
        def __init__(self):
            self.stdin = _FakeStdin()
            self.stdout = object()
            self.stderr = object()

        def poll(self):
            return None

        def terminate(self):
            events.append("terminate")

        def wait(self, timeout=None):
            events.append(f"wait:{timeout}")
            if timeout == 2:
                raise adapter.subprocess.TimeoutExpired(cmd="configured-grok", timeout=timeout)
            return 0

        def kill(self):
            events.append("kill")

    monkeypatch.setattr(adapter, "_mcp_command_args", lambda: (["configured-grok"], {"available": True}))
    monkeypatch.setattr(adapter.subprocess, "Popen", lambda *args, **kwargs: _FakeProcess())
    monkeypatch.setattr(adapter.threading, "Thread", lambda *args, **kwargs: type("T", (), {"start": lambda self: None})())
    monkeypatch.setattr(adapter, "_write_jsonrpc", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        adapter,
        "_read_jsonrpc_response",
        lambda **kwargs: {"result": {"structuredContent": {"ok": True}}},
    )

    adapter._call_mcp_tool("web_search", {"query": "AUV"}, timeout_seconds=5)

    assert events == ["stdin.close", "terminate", "wait:2", "kill", "wait:5"]


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


def test_normalize_grok_payload_quarantines_empty_title_regex_only_doi():
    accepted, evidence = adapter.normalize_grok_payload(
        {
            "sources": [
                {
                    "title": "",
                    "content": "Search results mention 10.1145/1234567 but no paper metadata.",
                    "url": "https://example.org/search?q=paper",
                }
            ]
        },
        query="robotics control",
        index=1,
    )

    assert accepted == []
    assert evidence[0]["quality_state"] == "quarantined"
    assert evidence[0]["reason"] == "page_chrome_or_non_paper_extraction"


def test_normalize_grok_payload_treats_regex_only_arxiv_as_evidence():
    accepted, evidence = adapter.normalize_grok_payload(
        {
            "sources": [
                {
                    "title": "Generic profile page",
                    "content": "This page links arXiv:2401.12345 among many unrelated entries.",
                    "url": "https://example.org/profile",
                }
            ]
        },
        query="robotics control",
        index=1,
    )

    assert accepted == []
    assert evidence[0]["quality_state"] == "evidence_only"
    assert evidence[0]["reason"] == "regex_identifier_without_support"


def test_normalize_grok_payload_accepts_strong_doi_identity():
    accepted, evidence = adapter.normalize_grok_payload(
        {
            "sources": [
                {
                    "title": "Learning Robust Robot Control",
                    "doi": "10.1000/robot-control",
                    "url": "https://doi.org/10.1000/robot-control",
                    "snippet": "A peer-reviewed control paper.",
                }
            ]
        },
        query="robotics control",
        index=1,
    )

    assert evidence == []
    assert accepted[0]["title"] == "Learning Robust Robot Control"
    assert accepted[0]["doi"] == "10.1000/robot-control"
    assert accepted[0]["grok_quality_state"] == "candidate_usable"


def test_discover_grok_retries_source_fallback_and_records_recovery(tmp_path, monkeypatch):
    calls = []

    monkeypatch.setattr(adapter, "_mcp_command_args", lambda: (["configured-grok"], {"available": True}))

    def fake_call(*, arguments, timeout_seconds, **kwargs):
        calls.append(arguments["query"])
        if len(calls) == 1:
            return (
                {
                    "payload": {
                        "search_provider": "source_fallback",
                        "fallback_used": True,
                        "fallback_reason": "grok_provider_error",
                        "sources": [
                            {
                                "title": "Fallback Robot Paper",
                                "doi": "10.1000/fallback",
                                "url": "https://doi.org/10.1000/fallback",
                            }
                        ],
                    },
                    "raw_response": {"id": 1},
                },
                [{"model": "safe-model", "status": "retryable_fallback"}],
            )
        return (
            {
                "payload": {
                    "search_provider": "grok",
                    "fallback_used": False,
                    "sources": [
                        {
                            "title": "Recovered Robot Control Paper",
                            "doi": "10.1000/recovered",
                            "url": "https://doi.org/10.1000/recovered",
                        }
                    ],
                },
                "raw_response": {"id": 2},
            },
            [{"model": "safe-model", "status": "ok"}],
        )

    monkeypatch.setattr(adapter, "_call_web_search_with_model_fallbacks", fake_call)

    record = adapter.discover_grok(
        queries=["robotics control"],
        include_domains=["doi.org"],
        raw_response_path=tmp_path / "raw.json",
        evidence_path=tmp_path / "evidence.json",
        timeout_seconds=5,
    )

    assert calls[1].endswith("scholarly article DOI arXiv publisher metadata")
    assert [item["title"] for item in record["records"]] == ["Recovered Robot Control Paper"]
    assert record["diagnostics"]["retry_outcome"] == "recovered"
    assert record["diagnostics"]["retry_attempts"][0]["reason"] == "source_fallback_or_low_confidence_provider_output"
    assert record["diagnostics"]["retry_attempts"][0]["status"] == "recovered"
    assert record["diagnostics"]["evidence_only_count"] == 1


def test_discover_grok_bounds_model_fallbacks_by_shared_timeout_budget(tmp_path, monkeypatch):
    now = {"value": 100.0}
    calls = []

    monkeypatch.setattr(adapter, "_mcp_command_args", lambda: (["configured-grok"], {"available": True}))
    monkeypatch.setattr(adapter, "_configured_model_fallbacks", lambda: ["m1", "m2", "m3"])
    monkeypatch.setattr(adapter.time, "monotonic", lambda: now["value"])

    def fake_call(tool_name, arguments, timeout_seconds, **kwargs):
        calls.append(timeout_seconds)
        now["value"] += 4.0
        return {
            "payload": {
                "search_provider": "source_fallback",
                "fallback_used": True,
                "fallback_reason": "grok_provider_error",
                "sources": [],
                "sources_count": 0,
            },
            "raw_response": {"ok": True},
        }

    monkeypatch.setattr(adapter, "_call_mcp_tool", fake_call)

    record = adapter.discover_grok(
        queries=["AUV control"],
        include_domains=[],
        raw_response_path=tmp_path / "raw.json",
        evidence_path=tmp_path / "evidence.json",
        timeout_seconds=5,
    )

    assert calls == [5, 1]
    assert record["diagnostics"]["failure_stage"] == "timeout_or_budget_cutoff"
    assert record["diagnostics"]["retry_outcome"] == "not_retryable"
