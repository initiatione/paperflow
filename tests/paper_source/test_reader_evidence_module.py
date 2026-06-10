import json

from paper_source.claim_support import build_claim_support_map
from paper_source.reader_evidence import validate_claim_support_map, validate_evidence_map, validate_reader_evidence


def _write_reader_evidence_fixture(tmp_path):
    paper_root = tmp_path / "paper"
    mineru_dir = paper_root / "mineru"
    reader_dir = paper_root / "reader"
    images_dir = mineru_dir / "images"
    images_dir.mkdir(parents=True)
    reader_dir.mkdir(parents=True)

    (paper_root / "metadata.json").write_text(
        json.dumps(
            {
                "title": "Grounded Embodied Control",
                "venue": "IROS",
                "sources": ["code", "dataset"],
            }
        ),
        encoding="utf-8",
    )
    (mineru_dir / "paper.md").write_text(
        "# Abstract\n\nGrounded claim.\n\n## Method\n\nGrounded method.\n",
        encoding="utf-8",
    )
    (images_dir / "figure-1.png").write_bytes(b"png")
    (reader_dir / "reader.md").write_text("# Reader\n", encoding="utf-8")
    (reader_dir / "reproducibility.md").write_text("# Reproducibility\n", encoding="utf-8")
    evidence_map = {
        "schema_version": "paper-source-reader-evidence-map-v1",
        "reader_roles": [
            "nature-sci-editor",
            "peer-reviewer",
            "senior-domain-researcher",
        ],
        "required_artifacts": [
            "reader/reader.md",
            "reader/reproducibility.md",
        ],
        "claims": [
            {
                "claim_id": "claim-001",
                "reader_role": "nature-sci-editor",
                "reader_artifact": "reader/reader.md",
                "claim": "Grounded claim.",
                "source": "mineru/paper.md",
                "locator": {"heading": "Abstract"},
                "evidence_address": "source=mineru/paper.md; heading=Abstract",
            },
            {
                "claim_id": "claim-002",
                "reader_role": "peer-reviewer",
                "reader_artifact": "reader/reproducibility.md",
                "claim": "Source availability.",
                "source": "metadata.json",
                "locator": {"field": "sources"},
                "evidence_address": "source=metadata.json; field=sources",
            },
            {
                "claim_id": "claim-003",
                "reader_role": "senior-domain-researcher",
                "reader_artifact": "reader/reader.md",
                "claim": "Transfer judgment.",
                "source": "inference",
                "locator": {"basis": "domain-transfer"},
                "evidence_address": "source=inference; basis=domain-transfer",
            },
        ],
    }
    (reader_dir / "evidence-map.json").write_text(json.dumps(evidence_map), encoding="utf-8")
    (reader_dir / "claim-support.json").write_text(
        json.dumps(build_claim_support_map(paper_title="Grounded Embodied Control", claims=evidence_map["claims"])),
        encoding="utf-8",
    )
    return paper_root


def test_reader_evidence_module_validates_markdown_evidence_addresses(tmp_path):
    paper_root = _write_reader_evidence_fixture(tmp_path)

    passed, evidence = validate_reader_evidence(
        paper_root,
        {
            "reader/reader.md": (
                "- Claim with paper heading.\n"
                "  Evidence: source=mineru/paper.md; heading=Abstract\n"
                "- Claim with figure.\n"
                "  Evidence: source=mineru/images; image=figure-1.png\n"
            ),
            "reader/reproducibility.md": (
                "- Claim with metadata.\n"
                "  Evidence: source=metadata.json; field=sources\n"
            ),
        },
    )

    assert passed is True
    assert evidence == ["Validated 3 structured reader evidence address(es)"]


def test_reader_evidence_module_rejects_evidence_map_without_all_reader_roles(tmp_path):
    paper_root = _write_reader_evidence_fixture(tmp_path)
    evidence_map_path = paper_root / "reader" / "evidence-map.json"
    payload = json.loads(evidence_map_path.read_text(encoding="utf-8"))
    payload["claims"] = [claim for claim in payload["claims"] if claim["reader_role"] != "senior-domain-researcher"]
    evidence_map_path.write_text(json.dumps(payload), encoding="utf-8")

    passed, evidence = validate_evidence_map(paper_root)

    assert passed is False
    assert any("missing claim(s) for reader role(s): senior-domain-researcher" in item for item in evidence)


def test_reader_evidence_module_validates_claim_support_statuses(tmp_path):
    paper_root = _write_reader_evidence_fixture(tmp_path)

    passed, evidence = validate_claim_support_map(paper_root, required=True)

    assert passed is True
    assert evidence == ["Validated 3 claim-support record(s) across 3 support status(es)"]


def test_reader_evidence_module_accepts_legacy_schema_versions(tmp_path):
    paper_root = _write_reader_evidence_fixture(tmp_path)
    reader_dir = paper_root / "reader"
    evidence_map_path = reader_dir / "evidence-map.json"
    support_path = reader_dir / "claim-support.json"
    evidence_map = json.loads(evidence_map_path.read_text(encoding="utf-8"))
    support = json.loads(support_path.read_text(encoding="utf-8"))
    evidence_map["schema_version"] = "epi-reader-evidence-map-v1"
    support["schema_version"] = "epi-claim-support-v1"
    evidence_map_path.write_text(json.dumps(evidence_map), encoding="utf-8")
    support_path.write_text(json.dumps(support), encoding="utf-8")

    map_passed, _ = validate_evidence_map(paper_root)
    support_passed, _ = validate_claim_support_map(paper_root, required=True)

    assert map_passed is True
    assert support_passed is True


def test_reader_evidence_module_validates_tex_manifest_and_pdf_sources(tmp_path):
    paper_root = _write_reader_evidence_fixture(tmp_path)
    mineru_dir = paper_root / "mineru"
    (paper_root / "paper.pdf").write_bytes(b"%PDF-1.4\nfixture\n")
    (mineru_dir / "paper.tex").write_text(
        "\\section{Method}\n\\begin{equation}v = \\omega r\\end{equation}\n",
        encoding="utf-8",
    )
    (mineru_dir / "mineru-manifest.json").write_text(
        json.dumps(
            {
                "batch_id": "source-first-batch",
                "outputs": [
                    {
                        "file_name": "paper.pdf",
                        "state": "done",
                        "image_count": 1,
                    }
                ],
                "warnings": ["formula parse should be checked against PDF"],
            }
        ),
        encoding="utf-8",
    )

    passed, evidence = validate_reader_evidence(
        paper_root,
        {
            "reader/technical-reading.md": (
                "- TeX formula cue detected: equation.\n"
                "  Evidence: source=mineru/paper.tex; cue=equation\n"
                "- MinerU manifest reports parse output state.\n"
                "  Evidence: source=mineru/mineru-manifest.json; output=paper.pdf; field=state\n"
                "- MinerU manifest reports parse warning metadata.\n"
                "  Evidence: source=mineru/mineru-manifest.json; field=warnings\n"
                "- PDF fallback artifact is available for parse checks.\n"
                "  Evidence: source=paper.pdf; field=available\n"
            ),
        },
    )

    assert passed is True
    assert evidence == ["Validated 4 structured reader evidence address(es)"]


def test_reader_evidence_module_rejects_empty_tex_evidence_source(tmp_path):
    paper_root = _write_reader_evidence_fixture(tmp_path)
    mineru_dir = paper_root / "mineru"
    (mineru_dir / "paper.tex").write_text("", encoding="utf-8")

    passed, evidence = validate_reader_evidence(
        paper_root,
        {
            "reader/technical-reading.md": (
                "- TeX formula cue detected: equation.\n"
                "  Evidence: source=mineru/paper.tex; cue=equation\n"
            ),
        },
    )

    assert passed is False
    assert any("missing mineru TeX" in item for item in evidence)


def test_reader_evidence_map_and_claim_support_accept_source_first_optional_sources(tmp_path):
    paper_root = _write_reader_evidence_fixture(tmp_path)
    mineru_dir = paper_root / "mineru"
    reader_dir = paper_root / "reader"
    (paper_root / "paper.pdf").write_bytes(b"%PDF-1.4\nfixture\n")
    (mineru_dir / "paper.tex").write_text(
        "\\section{Method}\n\\begin{equation}v = \\omega r\\end{equation}\n",
        encoding="utf-8",
    )
    (mineru_dir / "mineru-manifest.json").write_text(
        json.dumps(
            {
                "batch_id": "source-first-batch",
                "outputs": [{"file_name": "paper.pdf", "state": "done"}],
            }
        ),
        encoding="utf-8",
    )
    claims = [
        {
            "claim_id": "claim-tex-001",
            "reader_role": "nature-sci-editor",
            "reader_artifact": "reader/reader.md",
            "claim": "TeX formula cue detected: equation.",
            "source": "mineru/paper.tex",
            "locator": {"cue": "equation"},
            "evidence_address": "source=mineru/paper.tex; cue=equation",
        },
        {
            "claim_id": "claim-manifest-001",
            "reader_role": "peer-reviewer",
            "reader_artifact": "reader/reproducibility.md",
            "claim": "MinerU manifest reports parse output state for paper.pdf.",
            "source": "mineru/mineru-manifest.json",
            "locator": {"output": "paper.pdf", "field": "state"},
            "evidence_address": "source=mineru/mineru-manifest.json; output=paper.pdf; field=state",
        },
        {
            "claim_id": "claim-pdf-001",
            "reader_role": "senior-domain-researcher",
            "reader_artifact": "reader/reader.md",
            "claim": "PDF fallback artifact is available for parse checks.",
            "source": "paper.pdf",
            "locator": {"field": "available"},
            "evidence_address": "source=paper.pdf; field=available",
        },
    ]
    (reader_dir / "evidence-map.json").write_text(
        json.dumps(
            {
                "schema_version": "paper-source-reader-evidence-map-v1",
                "reader_roles": [
                    "nature-sci-editor",
                    "peer-reviewer",
                    "senior-domain-researcher",
                ],
                "required_artifacts": [
                    "reader/reader.md",
                    "reader/reproducibility.md",
                ],
                "claims": claims,
            }
        ),
        encoding="utf-8",
    )
    (reader_dir / "claim-support.json").write_text(
        json.dumps(build_claim_support_map(paper_title="Grounded Embodied Control", claims=claims)),
        encoding="utf-8",
    )

    map_passed, map_evidence = validate_evidence_map(paper_root)
    support_passed, support_evidence = validate_claim_support_map(paper_root, required=True)

    claim_support = json.loads((reader_dir / "claim-support.json").read_text(encoding="utf-8"))
    by_source = {claim["source"]: claim for claim in claim_support["claims"]}
    assert map_passed is True
    assert map_evidence == ["Validated 3 evidence-map claim(s) across 3 reader role(s)"]
    assert support_passed is True
    assert support_evidence == ["Validated 3 claim-support record(s) across 2 support status(es)"]
    assert by_source["mineru/paper.tex"]["support_status"] == "source-grounded"
    assert by_source["mineru/mineru-manifest.json"]["support_status"] == "metadata-only"
    assert by_source["paper.pdf"]["support_status"] == "source-grounded"


def test_reader_evidence_module_rejects_stale_claim_support_status(tmp_path):
    paper_root = _write_reader_evidence_fixture(tmp_path)
    support_path = paper_root / "reader" / "claim-support.json"
    payload = json.loads(support_path.read_text(encoding="utf-8"))
    payload["claims"][0]["support_status"] = "metadata-only"
    support_path.write_text(json.dumps(payload), encoding="utf-8")

    passed, evidence = validate_claim_support_map(paper_root, required=True)

    assert passed is False
    assert any("support_status=metadata-only does not match source=mineru/paper.md" in item for item in evidence)
