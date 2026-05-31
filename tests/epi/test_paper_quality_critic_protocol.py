import json

from epi.run_critic import run_critics


def _write_role_reader_artifacts(reader_dir) -> None:
    (reader_dir / "editorial-summary.md").write_text(
        "# Editorial Summary\n\n"
        "## Central Claim\n"
        "- A grounded engineering claim.\n"
        "  Evidence: source=mineru/paper.md; heading=Abstract\n\n"
        "## Why It Matters\n"
        "- Venue/context: IROS.\n"
        "  Evidence: source=metadata.json; field=venue\n\n"
        "## Editorial Caveat\n"
        "- Inference: scope needs critic review.\n"
        "  Evidence: source=inference; basis=editorial-caveat\n",
        encoding="utf-8",
    )
    (reader_dir / "technical-reading.md").write_text(
        "# Technical Reading\n\n"
        "## Method Decomposition\n"
        "- A grounded engineering method needs review.\n"
        "  Evidence: source=mineru/paper.md; heading=Abstract\n\n"
        "## Reproducibility Hooks\n"
        "- Metadata is present.\n"
        "  Evidence: source=metadata.json; field=title\n\n"
        "## Reviewer Checkpoint\n"
        "- Inference: benchmark details need checking.\n"
        "  Evidence: source=inference; basis=technical-review-checkpoint\n",
        encoding="utf-8",
    )
    (reader_dir / "research-notes.md").write_text(
        "# Research Notes\n\n"
        "## Fit To Research Direction\n"
        "- Inference: relevant to robotics research.\n"
        "  Evidence: source=inference; basis=research-fit\n\n"
        "## Follow-up Experiments\n"
        "- Inference: use for future ablations.\n"
        "  Evidence: source=inference; basis=follow-up-experiments\n",
        encoding="utf-8",
    )


def _write_protocol_fixture(
    tmp_path,
    *,
    metadata: dict,
    mineru_text: str,
    reader_text: str,
    technical_reading_text: str | None = None,
    figures_text: str = "# Figures\n\nNo figures were detected in mineru/images.\n",
    reproducibility_text: str = "# Reproducibility\n\nNo code or data availability was found.\n",
):
    paper_root = tmp_path / "_raw" / "papers" / "paper"
    mineru_dir = paper_root / "mineru"
    reader_dir = paper_root / "reader"
    mineru_dir.mkdir(parents=True)
    reader_dir.mkdir(parents=True)

    (paper_root / "paper.pdf").write_bytes(b"%PDF-1.4\nfixture paper\n")
    (paper_root / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    (mineru_dir / "paper.md").write_text(mineru_text, encoding="utf-8")
    (reader_dir / "reader.md").write_text(reader_text, encoding="utf-8")
    (reader_dir / "figures.md").write_text(figures_text, encoding="utf-8")
    (reader_dir / "reproducibility.md").write_text(reproducibility_text, encoding="utf-8")
    _write_role_reader_artifacts(reader_dir)
    if technical_reading_text is not None:
        (reader_dir / "technical-reading.md").write_text(technical_reading_text, encoding="utf-8")
    (reader_dir / "evidence-map.json").write_text(
        json.dumps(
            {
                "schema_version": "epi-reader-evidence-map-v1",
                "paper_title": metadata.get("title", "Fixture Paper"),
                "reader_roles": [
                    "nature-sci-editor",
                    "peer-reviewer",
                    "senior-domain-researcher",
                ],
                "claims": [
                    {
                        "claim_id": "reader-claim-001",
                        "reader_role": "nature-sci-editor",
                        "reader_artifact": "reader/reader.md",
                        "claim": "A grounded engineering claim.",
                        "source": "mineru/paper.md",
                        "locator": {"heading": "Abstract"},
                        "evidence_address": "source=mineru/paper.md; heading=Abstract",
                    },
                    {
                        "claim_id": "reader-claim-002",
                        "reader_role": "peer-reviewer",
                        "reader_artifact": "reader/reproducibility.md",
                        "claim": "Reproducibility evidence was inspected.",
                        "source": "metadata.json",
                        "locator": {"field": "title"},
                        "evidence_address": "source=metadata.json; field=title",
                    },
                    {
                        "claim_id": "reader-claim-003",
                        "reader_role": "senior-domain-researcher",
                        "reader_artifact": "reader/reader.md",
                        "claim": "Research transfer requires judgment.",
                        "source": "inference",
                        "locator": {"basis": "implementation-ideas"},
                        "evidence_address": "source=inference; basis=implementation-ideas",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return paper_root


def _paper_reviewer(paper_root):
    quorum = json.loads((paper_root / "critic" / "critic-quorum.json").read_text(encoding="utf-8"))
    return next(reviewer for reviewer in quorum["reviewers"] if reviewer["name"] == "paper-quality-critic")


def _parse_reviewer(paper_root):
    quorum = json.loads((paper_root / "critic" / "critic-quorum.json").read_text(encoding="utf-8"))
    return next(reviewer for reviewer in quorum["reviewers"] if reviewer["name"] == "parse-quality-critic")


def _stable_metadata(**overrides):
    metadata = {
        "slug": "paper",
        "title": "Reliable Engineering Paper",
        "doi": "10.1000/robotics",
        "venue": "IROS",
        "pdf_url": "https://example.org/paper.pdf",
    }
    metadata.update(overrides)
    return metadata


def test_paper_quality_rejects_missing_stable_paper_identity(tmp_path):
    paper_root = _write_protocol_fixture(
        tmp_path,
        metadata={"slug": "paper", "title": "Untethered Fixture"},
        mineru_text="# Abstract\n\nA grounded engineering claim.\n",
        reader_text=(
            "# Reader\n\n"
            "- Claim 1: The paper proposes a grounded engineering system.\n"
            "  Evidence: source=mineru/paper.md; heading=Abstract\n"
        ),
    )

    report = run_critics(paper_root)

    assert report["outcome"] == "revise-reader"
    assert report["checks"]["paper_quality"] is False
    reviewer = _paper_reviewer(paper_root)
    assert reviewer["verdict"] == "fail"
    assert any("paper_identity" in item and "missing stable identifier" in item for item in reviewer["evidence"])
    assert report["paper_quality_checks"]["paper_identity"]["status"] == "fail"


def test_parse_quality_records_source_first_companion_artifacts_when_available(tmp_path):
    paper_root = _write_protocol_fixture(
        tmp_path,
        metadata=_stable_metadata(),
        mineru_text="# Abstract\n\nA grounded engineering claim.\n",
        reader_text=(
            "# Reader\n\n"
            "- Claim 1: The paper proposes a grounded engineering system.\n"
            "  Evidence: source=mineru/paper.md; heading=Abstract\n"
        ),
    )
    mineru_dir = paper_root / "mineru"
    images_dir = mineru_dir / "images"
    images_dir.mkdir(exist_ok=True)
    (mineru_dir / "paper.tex").write_text("\\section{Abstract}\n\\begin{equation}x=1\\end{equation}\n", encoding="utf-8")
    (mineru_dir / "mineru-manifest.json").write_text(
        json.dumps({"outputs": [{"file_name": "paper.pdf", "state": "done"}]}),
        encoding="utf-8",
    )
    (images_dir / "figure-1.png").write_bytes(b"png")
    (paper_root / "parse-record.json").write_text(
        json.dumps({"status": "success", "image_count": 1, "tex_source": "mineru-native"}),
        encoding="utf-8",
    )

    report = run_critics(paper_root)

    assert report["outcome"] == "pass"
    assert report["checks"]["parse_quality"] is True
    assert report["parse_quality_checks"]["mineru_paper_tex_ready"] is True
    assert report["parse_quality_checks"]["mineru_manifest_ready"] is True
    assert report["parse_quality_checks"]["mineru_image_file_count"] == 1
    reviewer = _parse_reviewer(paper_root)
    assert reviewer["verdict"] == "pass"
    assert any("mineru/paper.tex exists" in item for item in reviewer["evidence"])
    assert any("mineru/mineru-manifest.json exists" in item for item in reviewer["evidence"])
    assert any("mineru/images file_count=1" in item for item in reviewer["evidence"])


def test_parse_quality_fails_successful_parse_without_tex_or_manifest(tmp_path):
    paper_root = _write_protocol_fixture(
        tmp_path,
        metadata=_stable_metadata(),
        mineru_text="# Abstract\n\nA grounded engineering claim.\n",
        reader_text=(
            "# Reader\n\n"
            "- Claim 1: The paper proposes a grounded engineering system.\n"
            "  Evidence: source=mineru/paper.md; heading=Abstract\n"
        ),
    )
    (paper_root / "parse-record.json").write_text(
        json.dumps({"status": "success", "image_count": 0}),
        encoding="utf-8",
    )

    report = run_critics(paper_root)

    assert report["outcome"] == "revise-reader"
    assert report["checks"]["parse_quality"] is False
    assert report["parse_quality_checks"]["mineru_paper_tex_ready"] is False
    assert report["parse_quality_checks"]["mineru_manifest_ready"] is False
    reviewer = _parse_reviewer(paper_root)
    assert reviewer["verdict"] == "fail"
    assert any("mineru_paper_tex_ready" in item for item in reviewer["evidence"])
    assert any("mineru_manifest_ready" in item for item in reviewer["evidence"])


def test_paper_quality_rejects_placeholder_url_as_stable_paper_identity(tmp_path):
    paper_root = _write_protocol_fixture(
        tmp_path,
        metadata={"slug": "paper", "title": "Untethered Fixture", "url": "not available"},
        mineru_text="# Abstract\n\nA grounded engineering claim.\n",
        reader_text=(
            "# Reader\n\n"
            "- Claim 1: The paper proposes a grounded engineering system.\n"
            "  Evidence: source=mineru/paper.md; heading=Abstract\n"
        ),
    )

    report = run_critics(paper_root)

    assert report["outcome"] == "revise-reader"
    reviewer = _paper_reviewer(paper_root)
    assert any("paper_identity" in item and "missing stable identifier" in item for item in reviewer["evidence"])
    assert report["paper_quality_checks"]["paper_identity"]["status"] == "fail"


def test_paper_quality_rejects_core_claim_without_local_evidence_line(tmp_path):
    paper_root = _write_protocol_fixture(
        tmp_path,
        metadata=_stable_metadata(),
        mineru_text="# Abstract\n\nA grounded engineering claim.\n",
        reader_text=(
            "# Reader\n\n"
            "- Claim 1: The core contribution is an adaptive controller for embodied robots.\n"
            "- Claim 2: The paper includes a validated method.\n"
            "  Evidence: source=mineru/paper.md; heading=Abstract\n"
        ),
    )

    report = run_critics(paper_root)

    assert report["outcome"] == "revise-reader"
    reviewer = _paper_reviewer(paper_root)
    assert reviewer["verdict"] == "fail"
    assert any("claim_support" in item and "Claim 1" in item for item in reviewer["evidence"])
    assert report["paper_quality_checks"]["claim_support"]["status"] == "fail"


def test_paper_quality_rejects_role_reader_claim_without_local_evidence_line(tmp_path):
    paper_root = _write_protocol_fixture(
        tmp_path,
        metadata=_stable_metadata(),
        mineru_text="# Abstract\n\nA grounded engineering claim.\n",
        reader_text=(
            "# Reader\n\n"
            "- Claim 1: The paper proposes a grounded engineering system.\n"
            "  Evidence: source=mineru/paper.md; heading=Abstract\n"
        ),
        technical_reading_text=(
            "# Technical Reading\n\n"
            "## Method Decomposition\n"
            "- Claim 2: The method outperforms prior baselines by 12% on the navigation benchmark.\n"
        ),
    )

    report = run_critics(paper_root)

    assert report["outcome"] == "revise-reader"
    reviewer = _paper_reviewer(paper_root)
    assert any("claim_support" in item and "Claim 2" in item for item in reviewer["evidence"])
    assert report["paper_quality_checks"]["claim_support"]["status"] == "fail"


def test_paper_quality_requires_benchmark_context_for_outperform_sota_claims(tmp_path):
    paper_root = _write_protocol_fixture(
        tmp_path,
        metadata=_stable_metadata(),
        mineru_text="# Abstract\n\nThe method outperforms prior SOTA approaches.\n",
        reader_text=(
            "# Reader\n\n"
            "- Claim 1: The method outperforms prior SOTA approaches.\n"
            "  Evidence: source=mineru/paper.md; heading=Abstract\n"
        ),
    )

    report = run_critics(paper_root)

    assert report["outcome"] == "revise-reader"
    reviewer = _paper_reviewer(paper_root)
    assert reviewer["verdict"] == "fail"
    assert any("benchmark_integrity" in item and "baseline" in item for item in reviewer["evidence"])
    assert any("benchmark_integrity" in item and "metric" in item for item in reviewer["evidence"])
    assert any("benchmark_integrity" in item and "dataset/task" in item for item in reviewer["evidence"])
    assert report["paper_quality_checks"]["benchmark_integrity"]["status"] == "fail"


def test_paper_quality_does_not_use_unrelated_benchmark_terms_for_performance_claim(tmp_path):
    paper_root = _write_protocol_fixture(
        tmp_path,
        metadata=_stable_metadata(),
        mineru_text=(
            "# Abstract\n\n"
            "The method outperforms prior SOTA approaches.\n\n"
            "## Appendix\n\n"
            "This appendix defines common words: baseline, metric, and dataset.\n"
        ),
        reader_text=(
            "# Reader\n\n"
            "- Claim 1: The method outperforms prior SOTA approaches.\n"
            "  Evidence: source=mineru/paper.md; heading=Abstract\n"
        ),
    )

    report = run_critics(paper_root)

    assert report["outcome"] == "revise-reader"
    reviewer = _paper_reviewer(paper_root)
    assert reviewer["verdict"] == "fail"
    assert any("benchmark_integrity" in item and "baseline" in item for item in reviewer["evidence"])
    assert any("benchmark_integrity" in item and "metric" in item for item in reviewer["evidence"])
    assert any("benchmark_integrity" in item and "dataset/task" in item for item in reviewer["evidence"])
    assert report["paper_quality_checks"]["benchmark_integrity"]["status"] == "fail"


def test_paper_quality_does_not_fail_when_only_source_survey_mentions_improvement(tmp_path):
    paper_root = _write_protocol_fixture(
        tmp_path,
        metadata=_stable_metadata(title="Robotics Foundation Model Survey"),
        mineru_text=(
            "# Abstract\n\n"
            "This survey reviews foundation models for robotics and discusses how recent systems "
            "can improve planning, control, and generalization in embodied AI.\n\n"
            "# Benchmarks\n\n"
            "The paper catalogs datasets, simulators, and benchmarks without making a new method-level "
            "outperform claim in the reader artifact.\n"
        ),
        reader_text=(
            "# Reader\n\n"
            "- Claim 1: The paper surveys foundation-model use in robotics and embodied AI.\n"
            "  Evidence: source=mineru/paper.md; heading=Abstract\n"
        ),
    )

    report = run_critics(paper_root)

    assert report["outcome"] == "pass"
    assert report["paper_quality_checks"]["benchmark_integrity"]["status"] == "pass"


def test_paper_quality_accepts_local_plural_baseline_metric_and_task_context(tmp_path):
    paper_root = _write_protocol_fixture(
        tmp_path,
        metadata=_stable_metadata(),
        mineru_text=(
            "# Abstract\n\n"
            "A grounded engineering claim.\n\n"
            "# Results\n\n"
            "The method outperforms prior baselines by 12% on a navigation benchmark.\n"
        ),
        reader_text=(
            "# Reader\n\n"
            "- Claim 1: The method outperforms prior baselines by 12% on a navigation benchmark.\n"
            "  Evidence: source=mineru/paper.md; heading=Results\n"
        ),
    )

    report = run_critics(paper_root)

    assert report["outcome"] == "pass"
    assert report["paper_quality_checks"]["benchmark_integrity"]["status"] == "pass"


def test_paper_quality_records_engineering_reproducibility_gaps_as_warnings(tmp_path):
    paper_root = _write_protocol_fixture(
        tmp_path,
        metadata=_stable_metadata(),
        mineru_text="# Abstract\n\nA grounded engineering claim.\n",
        reader_text=(
            "# Reader\n\n"
            "- Claim 1: The paper proposes a grounded engineering system.\n"
            "  Evidence: source=mineru/paper.md; heading=Abstract\n"
        ),
    )

    report = run_critics(paper_root)

    assert report["outcome"] == "pass"
    reviewer = _paper_reviewer(paper_root)
    assert reviewer["verdict"] == "pass"
    assert any("engineering_reproducibility" in item and "missing" in item for item in reviewer["warnings"])
    assert report["paper_quality_checks"]["engineering_reproducibility"]["status"] == "warning"


def test_paper_quality_warns_when_parse_limitations_could_be_mistaken_for_paper_absence(tmp_path):
    paper_root = _write_protocol_fixture(
        tmp_path,
        metadata=_stable_metadata(),
        mineru_text="# Abstract\n\nA grounded engineering claim. [Formula omitted during parsing]\n",
        reader_text=(
            "# Reader\n\n"
            "- Claim 1: The paper proposes a grounded engineering system.\n"
            "  Evidence: source=mineru/paper.md; heading=Abstract\n"
        ),
    )

    report = run_critics(paper_root)

    assert report["outcome"] == "pass"
    reviewer = _paper_reviewer(paper_root)
    assert any("parse_vs_paper_failure" in item and "MinerU parse limitation" in item for item in reviewer["warnings"])
    assert report["paper_quality_checks"]["parse_vs_paper_failure"]["status"] == "warning"


def test_paper_quality_rejects_scope_overclaim_from_simulation_to_real_deployment(tmp_path):
    paper_root = _write_protocol_fixture(
        tmp_path,
        metadata=_stable_metadata(),
        mineru_text="# Abstract\n\nSimulation results show a small-scale robot demo.\n",
        reader_text=(
            "# Reader\n\n"
            "- Claim 1: Simulation results prove the controller is ready for real-world deployment across all robots.\n"
            "  Evidence: source=mineru/paper.md; heading=Abstract\n"
        ),
    )

    report = run_critics(paper_root)

    assert report["outcome"] == "revise-reader"
    reviewer = _paper_reviewer(paper_root)
    assert reviewer["verdict"] == "fail"
    assert any("scope_overclaim" in item for item in reviewer["evidence"])
    assert report["paper_quality_checks"]["scope_overclaim"]["status"] == "fail"
