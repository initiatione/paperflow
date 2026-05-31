from __future__ import annotations

from pathlib import Path


ROLE_CRITIC_SPECS = [
    {
        "name": "editorial-significance-critic",
        "lens": "nature-sci-editor",
        "scope": "Nature/Sci editorial significance, novelty framing, broad-interest claim discipline",
        "consumes": "reader/editorial-summary.md",
        "required_sections": ["## Central Claim", "## Why It Matters", "## Editorial Caveat"],
    },
    {
        "name": "peer-review-methods-critic",
        "lens": "peer-reviewer",
        "scope": "peer-review methods, evidence, benchmark, and reproducibility discipline",
        "consumes": "reader/technical-reading.md",
        "required_sections": ["## Method Decomposition", "## Reproducibility Hooks", "## Reviewer Checkpoint"],
    },
    {
        "name": "domain-fit-critic",
        "lens": "senior-domain-researcher",
        "scope": "senior researcher fit to the user's configured research profile and agenda",
        "consumes": "reader/research-notes.md",
        "required_sections": ["## Fit To Research Direction", "## Follow-up Experiments"],
    },
]


def role_reviewer_paths(critic_dir: Path) -> dict[str, Path]:
    return {
        "editorial-significance-critic.md": critic_dir / "editorial-significance-critic.md",
        "peer-review-methods-critic.md": critic_dir / "peer-review-methods-critic.md",
        "domain-fit-critic.md": critic_dir / "domain-fit-critic.md",
    }


def role_check_key(reviewer_name: str) -> str:
    return reviewer_name.removesuffix("-critic").replace("-", "_")


def review_role_artifacts(paper_root: Path) -> list[dict]:
    return [_review_role_artifact(paper_root, spec) for spec in ROLE_CRITIC_SPECS]


def _evidence_addresses(text: str) -> list[str]:
    addresses: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Evidence:"):
            addresses.append(stripped.removeprefix("Evidence:").strip())
    return addresses


def _reviewer_record(
    name: str,
    scope: str,
    passed: bool,
    evidence: list[str],
    review_protocol: dict,
) -> dict:
    return {
        "name": name,
        "mode": "local",
        "scope": scope,
        "verdict": "pass" if passed else "fail",
        "evidence": evidence,
        "warnings": [],
        "review_protocol": review_protocol,
    }


def _review_role_artifact(paper_root: Path, spec: dict) -> dict:
    artifact = spec["consumes"]
    path = paper_root / artifact
    evidence: list[str] = []
    failures: list[str] = []
    text = ""

    if path.exists():
        text = path.read_text(encoding="utf-8")
        evidence.append(f"{artifact} exists")
    else:
        failures.append(f"{artifact} missing")

    for section in spec["required_sections"]:
        if section in text:
            evidence.append(f"{artifact} contains required section: {section}")
        else:
            failures.append(f"{artifact} missing required section: {section}")

    evidence_count = len(_evidence_addresses(text))
    if evidence_count:
        evidence.append(f"{artifact} contains {evidence_count} structured Evidence line(s)")
    else:
        failures.append(f"{artifact} missing structured Evidence lines")

    return _reviewer_record(
        spec["name"],
        spec["scope"],
        not failures,
        failures or evidence,
        review_protocol={
            "lens": spec["lens"],
            "consumes": artifact,
            "required_sections": spec["required_sections"],
        },
    )
