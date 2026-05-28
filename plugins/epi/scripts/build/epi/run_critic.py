from __future__ import annotations

import json
from pathlib import Path

from epi.artifacts import file_sha256, utc_now, write_json_atomic, write_text_atomic


HARD_RULE = "No critic pass, no compiled wiki write."
TOOL_VERSIONS = {
    "critic_pipeline": "epi-local-static-v1",
}


def _mineru_headings(mineru_text: str) -> set[str]:
    headings: set[str] = set()
    for line in mineru_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        heading = stripped.lstrip("#").strip()
        if heading:
            headings.add(heading)
    return headings


def _evidence_addresses(text: str) -> list[str]:
    addresses: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Evidence:"):
            addresses.append(stripped.removeprefix("Evidence:").strip())
    return addresses


def _parse_evidence_address(address: str) -> dict[str, str] | None:
    fields: dict[str, str] = {}
    for segment in address.split(";"):
        part = segment.strip()
        if not part or "=" not in part:
            return None
        key, value = part.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            return None
        fields[key] = value
    return fields if "source" in fields else None


def _validate_reader_evidence(paper_root: Path, evidence_docs: dict[str, str]) -> tuple[bool, list[str]]:
    addresses: list[tuple[str, str]] = []
    for doc_name, text in evidence_docs.items():
        addresses.extend((doc_name, address) for address in _evidence_addresses(text))
    if not addresses:
        return False, ["reader outputs missing structured Evidence lines"]

    metadata = json.loads((paper_root / "metadata.json").read_text(encoding="utf-8"))
    mineru_text = (paper_root / "mineru" / "paper.md").read_text(encoding="utf-8")
    headings = _mineru_headings(mineru_text)
    failures: list[str] = []

    for doc_name, address in addresses:
        parsed = _parse_evidence_address(address)
        if not parsed:
            failures.append(f"{doc_name}: unsupported evidence address: {address}")
            continue

        source = parsed["source"]
        if source == "mineru/paper.md":
            heading = parsed.get("heading")
            if not heading or heading not in headings:
                failures.append(f"{doc_name}: missing mineru heading for Evidence: {address}")
        elif source == "metadata.json":
            field = parsed.get("field")
            if not field or field not in metadata:
                failures.append(f"{doc_name}: missing metadata field for Evidence: {address}")
        elif source == "mineru/images":
            image = parsed.get("image")
            image_path = paper_root / "mineru" / "images" / image if image else None
            if not image or image_path is None or not image_path.exists():
                failures.append(f"{doc_name}: missing mineru image for Evidence: {address}")
        elif source == "inference":
            basis = parsed.get("basis")
            if not basis:
                failures.append(f"{doc_name}: missing inference basis for Evidence: {address}")
        else:
            failures.append(f"{doc_name}: unsupported evidence source for Evidence: {address}")

    if failures:
        return False, failures
    return True, [f"Validated {len(addresses)} structured reader evidence address(es)"]


def _reviewer_record(name: str, scope: str, passed: bool, evidence: list[str]) -> dict:
    return {
        "name": name,
        "mode": "local",
        "scope": scope,
        "verdict": "pass" if passed else "fail",
        "evidence": evidence,
    }


def _artifact_hashes(artifacts: dict[str, Path]) -> dict[str, str]:
    return {
        name: file_sha256(path)
        for name, path in artifacts.items()
        if path.exists()
    }


def run_critics(paper_root: Path) -> dict:
    started_at = utc_now()
    critic_dir = paper_root / "critic"
    critic_dir.mkdir(parents=True, exist_ok=True)
    reader_path = paper_root / "reader" / "reader.md"
    figures_path = paper_root / "reader" / "figures.md"
    reproducibility_path = paper_root / "reader" / "reproducibility.md"
    reader_text = reader_path.read_text(encoding="utf-8") if reader_path.exists() else ""
    reader_quality = False
    if reader_path.exists():
        reader_quality, reader_evidence = _validate_reader_evidence(
            paper_root,
            {
                "reader/reader.md": reader_text,
                "reader/figures.md": figures_path.read_text(encoding="utf-8") if figures_path.exists() else "",
                "reader/reproducibility.md": (
                    reproducibility_path.read_text(encoding="utf-8") if reproducibility_path.exists() else ""
                ),
            },
        )
    else:
        reader_evidence = ["reader/reader.md missing"]
    checks = {
        "paper_quality": (paper_root / "paper.pdf").exists() and (paper_root / "metadata.json").exists(),
        "parse_quality": (paper_root / "mineru" / "paper.md").exists(),
        "reader_quality": reader_quality,
    }
    outcome = "pass" if all(checks.values()) else "revise-reader"
    reviewers = [
        _reviewer_record(
            "paper-quality-critic",
            "raw paper acquisition and metadata",
            checks["paper_quality"],
            ["paper.pdf exists", "metadata.json exists"],
        ),
        _reviewer_record(
            "parse-quality-critic",
            "MinerU parse materialization",
            checks["parse_quality"],
            ["mineru/paper.md exists"],
        ),
        _reviewer_record(
            "reader-quality-critic",
            "reader output source grounding",
            checks["reader_quality"],
            reader_evidence,
        ),
    ]
    disagreement = len({reviewer["verdict"] for reviewer in reviewers}) > 1
    exit_status = 0 if outcome == "pass" else 1
    reviewer_paths = {
        "paper-quality-critic.md": critic_dir / "paper-quality-critic.md",
        "parse-quality-critic.md": critic_dir / "parse-quality-critic.md",
        "reader-quality-critic.md": critic_dir / "reader-quality-critic.md",
    }
    quorum = {
        "stage": "critic-quorum",
        "critic_at": utc_now(),
        "mode": "local",
        "tool_versions": TOOL_VERSIONS,
        "reviewers": reviewers,
        "reviewer_count": len(reviewers),
        "disagreement": disagreement,
        "final_outcome": outcome,
        "hard_rule": HARD_RULE,
    }
    quorum_path = critic_dir / "critic-quorum.json"
    for filename, passed in {
        "paper-quality-critic.md": checks["paper_quality"],
        "parse-quality-critic.md": checks["parse_quality"],
        "reader-quality-critic.md": checks["reader_quality"],
    }.items():
        write_text_atomic(
            critic_dir / filename,
            f"# {filename.removesuffix('.md')}\n\nOutcome: {'pass' if passed else 'fail'}\n\nHard rule: {HARD_RULE}\n",
        )
    input_hashes = _artifact_hashes(
        {
            "paper.pdf": paper_root / "paper.pdf",
            "metadata.json": paper_root / "metadata.json",
            "mineru/paper.md": paper_root / "mineru" / "paper.md",
            "reader/reader.md": reader_path,
            "reader/figures.md": figures_path,
            "reader/reproducibility.md": reproducibility_path,
        }
    )
    finished_at = utc_now()
    quorum["started_at"] = started_at
    quorum["finished_at"] = finished_at
    quorum["exit_status"] = exit_status
    quorum["input_artifact_hashes"] = input_hashes
    quorum["output_artifact_hashes"] = _artifact_hashes(reviewer_paths)
    write_json_atomic(quorum_path, quorum)
    report = {
        "stage": "critic",
        "critic_at": finished_at,
        "outcome": outcome,
        "checks": checks,
        "hard_rule": HARD_RULE,
        "tool_versions": TOOL_VERSIONS,
        "reviewer_quorum_path": str(quorum_path),
        "reviewer_count": len(reviewers),
        "disagreement": disagreement,
        "next_action": "stage" if outcome == "pass" else "revise-reader",
        "started_at": started_at,
        "finished_at": finished_at,
        "exit_status": exit_status,
        "input_artifact_hashes": input_hashes,
        "output_artifact_hashes": {
            **_artifact_hashes(reviewer_paths),
            "critic-quorum.json": file_sha256(quorum_path),
        },
    }
    write_json_atomic(critic_dir / "critic-report.json", report)
    return report
