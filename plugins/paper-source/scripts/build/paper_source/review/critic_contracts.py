from __future__ import annotations

from copy import deepcopy

from paper_source.source_artifacts import MINERU_MARKDOWN_ARTIFACT_LABEL


CORE_CRITIC_PROTOCOLS = {
    "paper-quality-critic": {
        "lens": "nature-sci-editor+senior-domain-researcher",
        "consumes": [
            "paper.pdf",
            "metadata.json",
            MINERU_MARKDOWN_ARTIFACT_LABEL,
            "reader/reader.md",
            "reader/figures.md",
            "reader/reproducibility.md",
        ],
        "hard_fail_checks": [
            "paper_identity",
            "claim_support",
            "benchmark_integrity",
            "scope_overclaim",
        ],
        "warning_checks": [
            "engineering_reproducibility",
            "parse_vs_paper_failure",
        ],
        "decision_boundary": "Reject unreliable paper identity, unsupported claims, incomplete benchmark claims, and scope overclaims; preserve reproducibility and parse gaps as warnings.",
    },
    "parse-quality-critic": {
        "lens": "parse-materialization-reviewer",
        "consumes": [
            "paper.pdf",
            MINERU_MARKDOWN_ARTIFACT_LABEL,
            "mineru/images",
            "mineru/mineru-manifest.json",
        ],
        "hard_fail_checks": [
            "mineru_paper_markdown_exists",
            "mineru_manifest_ready",
        ],
        "warning_checks": [
            "parse_record_missing",
            "mineru_paper_tex_missing",
            "mineru_manifest_missing",
            "mineru_images_missing",
            "mineru_images_empty",
        ],
        "decision_boundary": "Verify parsed material exists without treating parser omissions as proof that the original paper lacks content.",
    },
    "reader-quality-critic": {
        "lens": "source-grounding-reviewer",
        "consumes": [
            "reader/reader.md",
            "reader/editorial-summary.md",
            "reader/technical-reading.md",
            "reader/research-notes.md",
            "reader/figures.md",
            "reader/reproducibility.md",
            "reader/implementation-ideas.md",
            "reader/evidence-map.json",
        ],
        "hard_fail_checks": [
            "structured_evidence_lines",
            "evidence_map_schema",
            "role_claim_coverage",
            "evidence_address_resolution",
        ],
        "warning_checks": [],
        "decision_boundary": "Reject reader outputs whose claims cannot be traced to metadata, parsed paper headings, parsed images, or explicit inference bases.",
    },
}


def critic_protocol(name: str) -> dict:
    return deepcopy(CORE_CRITIC_PROTOCOLS[name])
