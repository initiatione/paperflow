import json

from paper_source.report_run import write_report


def _ranked_candidate(
    title,
    *,
    doi="10.1000/example",
    include_doi=True,
    quality_tier="Tier A",
    decision="advance-candidate",
    abstract="Original provider abstract with method, task, evidence, and caveat.",
    pdf_url="https://example.org/paper.pdf",
    score=0.9,
    citation_count=17,
    citation_count_source="openalex",
    verified_metrics=None,
):
    if verified_metrics is None:
        verified_metrics = {"easyscholar": {"status": "matched", "source": "easyscholar"}}
    candidate = {
        "slug": title.lower().replace(" ", "-"),
        "title": title,
        "score": score,
        "venue": "ICRA",
        "year": 2025,
        "abstract": abstract,
        "pdf_url": pdf_url,
        "citation_count": citation_count,
        "citation_count_source": citation_count_source,
        "citation_count_status": "verified" if citation_count_source else "unverified",
        "citation_count_sources": [{"source": citation_count_source, "count": citation_count}]
        if citation_count_source
        else [],
        "verified_metrics": verified_metrics,
        "paper_type": "benchmark",
        "classification_confidence": 0.88,
        "quality_tier": quality_tier,
        "quality_gate": {
            "evidence": ["stable_identifier", "high_topic_fit"],
            "cautions": [],
            "blocking_reasons": [],
        },
        "ranking_protocol": {
            "decision": decision,
            "reasons": ["matched user profile", "strong evidence"],
            "cautions": [],
        },
        "ranking_rationale": {
            "recommendation": decision,
            "one_sentence": f"{title} has enough evidence for the requested topic.",
        },
    }
    if include_doi:
        candidate["doi"] = doi
    return candidate


def test_write_report_emits_required_sections_even_when_empty(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)

    write_report(
        run_dir,
        ranked=[
            {
                "title": "Embodied Navigation Control for Mobile Robots",
                "score": 0.91,
                "venue": "IROS",
                "year": 2024,
                "pdf_url": "https://example.org/nav.pdf",
            }
        ],
        errors=[],
        rejected=[],
        quarantined=[],
        critic_failures=[],
        budget_usage={"max_results": 5, "discovered_count": 1},
        wiki_pages_written=[],
        zotero_results={"status": "not_run", "records": []},
        next_actions=[],
    )

    report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    assert report_json["accepted"][0]["title"] == "Embodied Navigation Control for Mobile Robots"
    assert report_json["rejected"] == []
    assert report_json["quarantined"] == []
    assert report_json["critic_failures"] == []
    assert report_json["budget_usage"] == {"max_results": 5, "discovered_count": 1}
    assert report_json["wiki_pages_written"] == []
    assert report_json["zotero_results"] == {"status": "not_run", "records": []}
    assert report_json["next_actions"] == []

    report_md = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "## Budget Usage" in report_md
    assert "## Next Actions" in report_md


def test_write_report_emits_session_recommendations_contract_for_chat(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    ranked = [
        _ranked_candidate("Primary Paper 01", doi="10.1000/p1", score=0.99),
        _ranked_candidate(
            "Primary Paper 02",
            include_doi=False,
            score=0.98,
            citation_count=None,
            citation_count_source=None,
        ),
        _ranked_candidate("Primary Paper 03", doi="", score=0.97),
        _ranked_candidate(
            "Needs PDF Paper",
            doi="10.1000/needs-pdf",
            pdf_url="",
            score=0.96,
        )
        | {
            "staging_readiness": "needs_pdf",
            "readiness_reasons": ["missing_pdf"],
            "candidate_manual_urls": [{"kind": "publisher", "url": "https://publisher.example/needs-pdf"}],
        },
    ]
    ranked.extend(
        _ranked_candidate(f"Primary Paper {index:02d}", doi=f"10.1000/p{index}", score=0.95 - index / 100)
        for index in range(4, 12)
    )
    ranked.extend(
        [
            _ranked_candidate(
                "Review Candidate Paper",
                doi="10.1000/review",
                quality_tier="Tier B",
                decision="review-candidate",
                score=0.5,
            ),
            _ranked_candidate(
                "Tier C Appendix Paper",
                doi="10.1000/tier-c",
                quality_tier="Tier C",
                decision="advance-candidate",
                score=0.4,
            ),
            _ranked_candidate(
                "Review Candidate Missing DOI",
                include_doi=False,
                quality_tier="Tier B",
                decision="review-candidate",
                score=0.3,
            ),
        ]
    )

    write_report(
        run_dir,
        ranked=ranked,
        errors=[],
        workflow_type="paper-discovery-dry-run",
        run_id="dry-run-session",
        rejected=[
            {"title": "Duplicate", "filter_reasons": ["already_in_wiki:references/duplicate"]},
            {"title": "Off Domain", "filter_reasons": ["outside_domain"]},
            {"title": "Second Off Domain", "filter_reasons": ["outside_domain"]},
        ],
        discovery_context={"diagnostics_path": "vault/_paper_source/runs/dry-run-session/discovery-diagnostics.json"},
    )

    report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    report_md = (run_dir / "report.md").read_text(encoding="utf-8")
    session = report_json["session_recommendations"]

    assert session["schema_version"] == "paper-source-session-recommendations-v1"
    assert session["summary_policy"] == {
        "language": "zh",
        "producer": "calling_agent",
        "source": "original_abstract",
    }
    assert session["doi_required_policy"] == {
        "required_for": ["primary_recommendations", "review_appendix"],
        "missing_reason": "missing_required_doi",
    }
    assert len(session["primary_recommendations"]) == 10
    assert session["overflow"] == {
        "primary_total": 10,
        "hidden_count": 0,
        "full_artifact": "report.json",
    }
    assert [item["title"] for item in session["primary_recommendations"][:3]] == [
        "Primary Paper 01",
        "Needs PDF Paper",
        "Primary Paper 04",
    ]
    assert all(item["doi_status"] == "present" for item in session["primary_recommendations"])
    assert session["doi_filtered_summary"]["total"] == 3
    filtered_by_slug = {item["slug"]: item for item in session["doi_filtered_summary"]["items"]}
    assert filtered_by_slug["primary-paper-02"]["surface"] == "primary_recommendations"
    assert filtered_by_slug["primary-paper-02"]["reason"] == "missing_required_doi"
    assert filtered_by_slug["primary-paper-02"]["doi_status"] == "unverified"
    assert filtered_by_slug["primary-paper-02"]["quality_tier"] == "Tier A"
    assert filtered_by_slug["primary-paper-02"]["primary_url"] == "https://example.org/paper.pdf"
    assert filtered_by_slug["primary-paper-03"]["doi_status"] == "missing"
    assert filtered_by_slug["review-candidate-missing-doi"]["surface"] == "review_appendix"
    assert session["primary_recommendations"][0]["doi"] == "10.1000/p1"
    assert session["primary_recommendations"][0]["doi_status"] == "present"
    assert session["primary_recommendations"][0]["doi_url"] == "https://doi.org/10.1000/p1"
    assert session["primary_recommendations"][0]["primary_url"] == "https://example.org/paper.pdf"
    assert session["primary_recommendations"][0]["citation_count"] == 17
    assert session["primary_recommendations"][0]["citation_count_status"] == "verified"
    assert session["primary_recommendations"][0]["citation_count_source"] == "openalex"
    assert session["primary_recommendations"][0]["citation_count_sources"] == [{"source": "openalex", "count": 17}]
    assert session["primary_recommendations"][0]["verified_metrics"]["easyscholar"]["source"] == "easyscholar"
    assert session["primary_recommendations"][0]["verification_warnings"] == []
    assert session["primary_recommendations"][0]["original_abstract"].startswith("Original provider abstract")
    assert session["primary_recommendations"][0]["chinese_summary"]["status"] == "agent_generated_required"
    assert session["primary_recommendations"][0]["quality_reason"]["ranking_reasons"] == [
        "matched user profile",
        "strong evidence",
    ]
    assert session["primary_recommendations"][0]["pdf_status"] == "available"
    assert session["primary_recommendations"][0]["auto_staging_status"] == "not_run"
    assert session["primary_recommendations"][1]["pdf_status"] == "needs_pdf"
    assert {"kind": "publisher", "url": "https://publisher.example/needs-pdf"} in session[
        "primary_recommendations"
    ][1]["manual_download"]["links"]

    appendix_titles = [item["title"] for item in session["review_appendix"]]
    assert appendix_titles == ["Review Candidate Paper", "Tier C Appendix Paper"]
    assert all(item["doi_status"] == "present" for item in session["review_appendix"])
    assert "Review Candidate Paper" not in [item["title"] for item in session["primary_recommendations"]]
    assert "Tier C Appendix Paper" not in [item["title"] for item in session["primary_recommendations"]]
    assert session["review_appendix"][0]["appendix_reason"].startswith("Review Candidate Paper has enough evidence")
    assert session["review_appendix"][1]["appendix_reason"] == "Tier C"
    assert session["verification_summary"]["citation_count"] == {"verified": 10, "unverified": 0}
    assert session["verification_summary"]["venue_metrics"] == {"verified": 10, "unverified": 0}
    assert session["verification_summary"]["items_requiring_verification"] == []
    assert session["rejected_summary"] == {
        "total": 3,
        "reason_counts": [
            {"reason": "outside_domain", "count": 2},
            {"reason": "already_in_wiki:references/duplicate", "count": 1},
        ],
    }
    assert "## Session Recommendations" in report_md
    assert "Chinese summaries: generated by the calling agent from original_abstract." in report_md
    assert "primary_url: https://example.org/paper.pdf" in report_md
    assert "citations: 17 (status=verified, source=openalex)" in report_md
    assert "missing_required_doi: 3" in report_md
    assert "### Verification Summary" in report_md
    assert "citation_count: verified=10, unverified=0" in report_md


def test_session_recommendations_separate_existing_library_hits_from_new_recommendations(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)

    write_report(
        run_dir,
        ranked=[_ranked_candidate("New AUV Attitude Paper", doi="10.1000/new-auv")],
        errors=[],
        workflow_type="paper-discovery-dry-run",
        run_id="dry-run-existing",
        rejected=[
            {
                "slug": "existing-auv",
                "title": "Existing Strong AUV Paper",
                "year": 2024,
                "doi": "10.1000/existing",
                "filter_reasons": ["already_in_wiki:references/existing-auv.md"],
                "existing_library_match": {
                    "source_type": "wiki_reference_index",
                    "page": "references/existing-auv.md",
                    "source_id": "doi:10.1000/existing",
                },
            },
            {
                "slug": "existing-raw",
                "title": "Existing Raw AUV Paper",
                "year": 2023,
                "filter_reasons": ["already_in_library:existing-raw"],
                "existing_library_match": {
                    "source_type": "raw_library",
                    "slug": "existing-raw",
                },
            },
        ],
    )

    report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    report_md = (run_dir / "report.md").read_text(encoding="utf-8")
    session = report_json["session_recommendations"]

    assert [item["title"] for item in session["primary_recommendations"]] == ["New AUV Attitude Paper"]
    assert [item["title"] for item in session["existing_library_appendix"]] == [
        "Existing Strong AUV Paper",
        "Existing Raw AUV Paper",
    ]
    assert session["existing_library_appendix"][0]["existing_page"] == "references/existing-auv.md"
    assert session["existing_library_appendix"][1]["existing_slug"] == "existing-raw"
    assert "### Already In Library Or Wiki" in report_md
    assert "Existing Strong AUV Paper - already_in_wiki:references/existing-auv.md" in report_md


def test_write_report_groups_dry_run_candidates_by_research_queue(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)

    write_report(
        run_dir,
        ranked=[
            {
                "title": "Strong Embodied Control Paper",
                "score": 0.91,
                "venue": "ICRA",
                "year": 2025,
                "pdf_url": "https://example.org/strong.pdf",
                "paper_type": "benchmark",
                "quality_tier": "Tier A",
                "paper_classification": {"primary_type": "benchmark", "confidence": 0.69},
                "ranking_confidence": 0.82,
                "ranking_protocol": {
                    "decision": "advance-candidate",
                    "reasons": ["matched keywords: humanoid, control", "code availability signal present"],
                    "cautions": [],
                },
                "ranking_rationale": {
                    "one_sentence": "Advance for low-burden reading report and wiki deposition.",
                    "role_views": {
                        "nature_sci_editor": {"take": "Strong editorial fit."},
                        "peer_reviewer": {"take": "Benchmarks are inspectable."},
                        "senior_domain_researcher": {"take": "Good theory and experiment transfer."},
                    },
                    "wiki_deposition": {"value": "Create reference, concept, synthesis, and report pages."},
                },
            },
            {
                "title": "Interesting Simulation Paper",
                "score": 0.63,
                "venue": "Workshop",
                "year": 2025,
                "pdf_url": "https://example.org/review.pdf",
                "ranking_protocol": {
                    "decision": "review-candidate",
                    "reasons": ["matched keywords: control"],
                    "cautions": ["weak_reproducibility_signal"],
                },
            },
        ],
        errors=[],
        workflow_type="paper-discovery-dry-run",
        run_id="dry-run-001",
    )

    report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    report_md = (run_dir / "report.md").read_text(encoding="utf-8")

    assert [paper["title"] for paper in report_json["research_queue"]["advance_candidates"]] == [
        "Strong Embodied Control Paper"
    ]
    assert [paper["title"] for paper in report_json["research_queue"]["review_candidates"]] == [
        "Interesting Simulation Paper"
    ]
    assert report_json["research_queue"]["unknown_decision"] == []
    assert "## Research Queue" in report_md
    assert "### Advance Candidates" in report_md
    assert "Strong Embodied Control Paper - score 0.91" in report_md
    assert "paper_type: benchmark (confidence=0.69)" in report_md
    assert "quality_tier: Tier A" in report_md
    assert "ranking_confidence: 0.82" in report_md
    assert "reasons: matched keywords: humanoid, control; code availability signal present" in report_md
    assert "rationale: Advance for low-burden reading report and wiki deposition." in report_md
    assert "nature-sci-editor: Strong editorial fit." in report_md
    assert "peer-reviewer: Benchmarks are inspectable." in report_md
    assert "senior-domain-researcher: Good theory and experiment transfer." in report_md
    assert "### Review Candidates" in report_md
    assert "Interesting Simulation Paper - score 0.63" in report_md
    assert "cautions: weak_reproducibility_signal" in report_md


def test_write_report_surfaces_discovery_source_coverage(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)

    write_report(
        run_dir,
        ranked=[],
        errors=[],
        workflow_type="paper-discovery-dry-run",
        run_id="dry-run-sources",
        discovery_context={
            "query_strategy": "query_plan_multi_query",
            "source_coverage": {
                "sources_used": ["arxiv", "semantic", "openalex"],
                "source_results": {"arxiv": 3, "semantic": 0, "openalex": 1},
                "errors": {"semantic": "rate limited"},
                "raw_total": 5,
                "deduped_total": 4,
                "query_count": 2,
                "capabilities": {
                    "arxiv": {"download": "supported", "read": "supported"},
                    "semantic": {"download": "oa", "read": "oa"},
                    "openalex": {"download": "unsupported", "read": "info-only"},
                },
                "provider_readiness": {
                    "unpaywall": {"status": "missing_required_env", "env": "PAPER_SEARCH_MCP_UNPAYWALL_EMAIL"},
                    "google_scholar": {"status": "missing_optional_env", "env": "PAPER_SEARCH_MCP_GOOGLE_SCHOLAR_PROXY_URL"},
                },
            },
        },
    )

    report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    report_md = (run_dir / "report.md").read_text(encoding="utf-8")

    assert report_json["discovery_context"]["source_coverage"]["raw_total"] == 5
    assert "## Source Coverage" in report_md
    assert "- raw_total: 5" in report_md
    assert "- deduped_total: 4" in report_md
    assert "- query_count: 2" in report_md
    assert "- arxiv: 3" in report_md
    assert "- semantic: 0 (error: rate limited)" in report_md
    assert "- openalex: 1" in report_md
    assert "openalex capability: download=unsupported, read=info-only" in report_md
    assert "unpaywall: missing_required_env (PAPER_SEARCH_MCP_UNPAYWALL_EMAIL)" in report_md
    assert "google_scholar: missing_optional_env (PAPER_SEARCH_MCP_GOOGLE_SCHOLAR_PROXY_URL)" in report_md


def test_write_report_surfaces_source_health_and_timeout_budget(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)

    write_report(
        run_dir,
        ranked=[],
        errors=[],
        workflow_type="paper-discovery-dry-run",
        run_id="dry-run-health",
        discovery_context={
            "source_coverage": {
                "sources_used": ["semantic", "google_scholar"],
                "source_results": {"semantic": 2, "google_scholar": 0},
                "errors": {"google_scholar": "bot detection blocked request"},
                "raw_total": 2,
                "deduped_total": 2,
                "query_count": 1,
                "source_health": {
                    "semantic": {
                        "status": "ok",
                        "result_count": 2,
                        "error": None,
                        "duration_ms": None,
                        "timeout_budget_seconds": 180,
                    },
                    "google_scholar": {
                        "status": "failed",
                        "result_count": 0,
                        "error": "bot detection blocked request",
                        "duration_ms": None,
                        "timeout_budget_seconds": 45,
                    },
                },
                "timeout_budget_seconds": 180,
                "search_duration_ms": 2500,
            },
        },
    )

    report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    report_md = (run_dir / "report.md").read_text(encoding="utf-8")

    source_coverage = report_json["discovery_context"]["source_coverage"]
    assert source_coverage["timeout_budget_seconds"] == 180
    assert source_coverage["search_duration_ms"] == 2500
    assert source_coverage["source_health"]["google_scholar"]["timeout_budget_seconds"] == 45
    assert "- timeout_budget_seconds: 180" in report_md
    assert "- search_duration_ms: 2500" in report_md
    assert "- source_health:" in report_md
    assert "semantic: ok, results=2, timeout=180s" in report_md
    assert "google_scholar: failed, results=0, timeout=45s, error=bot detection blocked request" in report_md


def test_write_report_surfaces_source_routing_and_manual_download_cards(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    manual_card = {
        "slug": "publisher-only",
        "title": "Publisher Only Paper",
        "doi": "10.5555/publisher.only",
        "doi_url": "https://doi.org/10.5555/publisher.only",
        "candidate_manual_urls": [
            {"kind": "publisher", "url": "https://publisher.example/article"},
            {"kind": "doi", "url": "https://doi.org/10.5555/publisher.only"},
        ],
        "preferred_next_step": "Download the PDF through your organization/institution.",
    }

    write_report(
        run_dir,
        [],
        [],
        workflow_type="prepare-ranked",
        run_id="prepare-manual",
        paper_states=[
            {
                "slug": "publisher-only",
                "paper_slug": "publisher-only",
                "title": "Publisher Only Paper",
                "state": "acquire_failed",
                "last_action": "acquire",
                "next_action": "manual-download",
                "human_gate_required": True,
            }
        ],
        failed_papers=[
            {
                "slug": "publisher-only",
                "paper_slug": "publisher-only",
                "title": "Publisher Only Paper",
                "state": "acquire_failed",
                "next_action": "manual-download",
            }
        ],
        manual_downloads=[manual_card],
        discovery_context={
            "source_coverage": {
                "sources_used": ["semantic", "google_scholar", "unpaywall"],
                "source_routing": {
                    "selected_sources": ["semantic", "unpaywall"],
                    "demoted_sources": [{"source": "google_scholar", "reason": "unstable_source"}],
                    "provider_risks": [
                        {
                            "provider": "core",
                            "status": "missing_recommended_env",
                            "env": "PAPER_SEARCH_MCP_CORE_API_KEY",
                            "importance": "recommended",
                            "reason": "CORE works better with a free API key and may rate-limit keyless access.",
                        }
                    ],
                },
            }
        },
    )

    report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    report_md = (run_dir / "report.md").read_text(encoding="utf-8")

    assert report_json["manual_downloads"] == [manual_card]
    assert report_json["discovery_context"]["source_coverage"]["source_routing"]["selected_sources"] == [
        "semantic",
        "unpaywall",
    ]
    assert "## Manual Downloads" in report_md
    assert "Publisher Only Paper - manual-download-required" in report_md
    assert "doi: https://doi.org/10.5555/publisher.only" in report_md
    assert "manual link: https://publisher.example/article" in report_md
    assert "## Source Routing" in report_md
    assert "selected_sources: semantic, unpaywall" in report_md
    assert "demoted: google_scholar (unstable_source)" in report_md
    assert "risk: core missing_recommended_env (PAPER_SEARCH_MCP_CORE_API_KEY)" in report_md


def test_write_report_surfaces_reader_revision_plans_for_routed_runs(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)

    write_report(
        run_dir,
        [],
        [],
        workflow_type="advance-batch",
        run_id="batch-001",
        paper_states=[
            {
                "slug": "paper",
                "paper_slug": "paper",
                "title": "Needs Reader Repair",
                "state": "critic_failed",
                "last_action": "critic",
                "next_action": "revise-reader",
                "human_gate_required": False,
            }
        ],
        reader_revision_plans=[
            {
                "slug": "paper",
                "title": "Needs Reader Repair",
                "plan_path": "D:\\vault\\_raw\\papers\\paper\\critic\\reader-revision-plan.json",
                "next_action": "revise-reader",
                "blocking_count": 2,
                "warning_count": 1,
            }
        ],
    )

    report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    report_md = (run_dir / "report.md").read_text(encoding="utf-8")

    assert report_json["reader_revision_plans"] == [
        {
            "slug": "paper",
            "title": "Needs Reader Repair",
            "plan_path": "D:\\vault\\_raw\\papers\\paper\\critic\\reader-revision-plan.json",
            "next_action": "revise-reader",
            "blocking_count": 2,
            "warning_count": 1,
        }
    ]
    assert "## Reader Revision Plans" in report_md
    assert "Needs Reader Repair - revise-reader" in report_md
    assert "blocking repairs: 2" in report_md
    assert "warning follow-ups: 1" in report_md
    assert "reader-revision-plan.json" in report_md


def test_write_report_surfaces_reproducibility_caveats_for_routed_runs(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)

    plan = {
        "slug": "paper",
        "title": "Needs Evidence Review",
        "plan_path": "D:\\vault\\_raw\\papers\\paper\\critic\\reproduction-plan.json",
        "next_action": "prepare-reproduction-plan",
        "missing_count": 4,
        "human_gate_required": True,
    }

    write_report(
        run_dir,
        [],
        [],
        workflow_type="advance-batch",
        run_id="batch-001",
        paper_states=[
            {
                "slug": "paper",
                "paper_slug": "paper",
                "title": "Needs Evidence Review",
                "state": "critic_passed",
                "last_action": "critic",
                "next_action": "stage",
                "human_gate_required": False,
            }
        ],
        reproduction_plans=[plan],
    )

    report_json = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    report_md = (run_dir / "report.md").read_text(encoding="utf-8")

    assert report_json["reproduction_plans"] == [plan]
    assert "## Reproducibility Caveats" in report_md
    assert "Needs Evidence Review - review-reproducibility-caveats" in report_md
    assert "## Reproduction Plans" not in report_md
    assert "missing checklist items: 4" in report_md
    assert "reproduction-plan.json" in report_md
