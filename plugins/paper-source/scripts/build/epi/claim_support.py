from __future__ import annotations

from collections import Counter
from typing import Any

from epi.source_artifacts import MINERU_MARKDOWN_ARTIFACT_LABEL, is_mineru_markdown_artifact


SUPPORT_BY_SOURCE = {
    MINERU_MARKDOWN_ARTIFACT_LABEL: {
        "support_status": "source-grounded",
        "support_grade": "direct-text",
        "epistemic_status": "extracted",
    },
    "mineru/paper.tex": {
        "support_status": "source-grounded",
        "support_grade": "formula-or-notation",
        "epistemic_status": "extracted",
    },
    "mineru/images": {
        "support_status": "source-grounded",
        "support_grade": "visual-asset",
        "epistemic_status": "extracted",
    },
    "paper.pdf": {
        "support_status": "source-grounded",
        "support_grade": "pdf-fallback",
        "epistemic_status": "extracted",
    },
    "metadata.json": {
        "support_status": "metadata-only",
        "support_grade": "metadata",
        "epistemic_status": "metadata",
    },
    "mineru/mineru-manifest.json": {
        "support_status": "metadata-only",
        "support_grade": "parse-manifest",
        "epistemic_status": "metadata",
    },
    "inference": {
        "support_status": "inferred",
        "support_grade": "inference",
        "epistemic_status": "inferred",
    },
}


def classify_claim_support(source: str) -> dict[str, str]:
    if is_mineru_markdown_artifact(source):
        return dict(SUPPORT_BY_SOURCE[MINERU_MARKDOWN_ARTIFACT_LABEL])
    return dict(
        SUPPORT_BY_SOURCE.get(
            source,
            {
                "support_status": "unsupported",
                "support_grade": "unknown-source",
                "epistemic_status": "ambiguous",
            },
        )
    )


def support_record(claim: dict[str, Any]) -> dict[str, Any]:
    support = classify_claim_support(str(claim.get("source") or ""))
    return {
        "claim_id": claim.get("claim_id"),
        "reader_role": claim.get("reader_role"),
        "reader_artifact": claim.get("reader_artifact"),
        "claim": claim.get("claim"),
        "source": claim.get("source"),
        "locator": claim.get("locator"),
        "evidence_address": claim.get("evidence_address"),
        **support,
    }


def build_claim_support_map(*, paper_title: str, claims: list[dict[str, Any]]) -> dict[str, Any]:
    support_records = [support_record(claim) for claim in claims]
    counts = Counter(str(record["support_status"]) for record in support_records)
    return {
        "schema_version": "epi-claim-support-v1",
        "paper_title": paper_title,
        "support_counts": dict(sorted(counts.items())),
        "claims": support_records,
    }
