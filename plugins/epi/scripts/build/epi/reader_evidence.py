from __future__ import annotations

import json
from pathlib import Path

from epi.claim_support import classify_claim_support
from epi.source_artifacts import resolve_mineru_markdown_path


REQUIRED_READER_ROLES = {
    "nature-sci-editor",
    "peer-reviewer",
    "senior-domain-researcher",
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


def _evidence_address(parsed: dict[str, str]) -> str:
    return "; ".join(f"{key}={value}" for key, value in parsed.items())


def _validate_evidence_reference(
    paper_root: Path,
    label: str,
    parsed: dict[str, str],
    metadata: dict,
    headings: set[str],
) -> list[str]:
    source = parsed["source"]
    if source.startswith("mineru/") and source.endswith(".md"):
        heading = parsed.get("heading")
        if not heading or heading not in headings:
            return [f"{label}: missing mineru heading for Evidence: {_evidence_address(parsed)}"]
    elif source == "mineru/paper.tex":
        tex_path = paper_root / "mineru" / "paper.tex"
        cue = parsed.get("cue")
        if not tex_path.exists():
            return [f"{label}: missing mineru TeX for Evidence: {_evidence_address(parsed)}"]
        if not cue:
            return [f"{label}: missing TeX cue for Evidence: {_evidence_address(parsed)}"]
        tex_text = tex_path.read_text(encoding="utf-8", errors="ignore")
        if cue != "tex-source-available" and cue not in tex_text:
            return [f"{label}: TeX cue not found for Evidence: {_evidence_address(parsed)}"]
    elif source == "metadata.json":
        field = parsed.get("field")
        if not field or field not in metadata:
            return [f"{label}: missing metadata field for Evidence: {_evidence_address(parsed)}"]
    elif source == "mineru/mineru-manifest.json":
        failures = _validate_mineru_manifest_reference(paper_root, label, parsed)
        if failures:
            return failures
    elif source == "mineru/images":
        image = parsed.get("image")
        image_path = paper_root / "mineru" / "images" / image if image else None
        if not image or image_path is None or not image_path.exists():
            return [f"{label}: missing mineru image for Evidence: {_evidence_address(parsed)}"]
    elif source == "paper.pdf":
        field = parsed.get("field")
        if not field:
            return [f"{label}: missing PDF evidence field for Evidence: {_evidence_address(parsed)}"]
        pdf_path = paper_root / "paper.pdf"
        if not pdf_path.exists():
            return [f"{label}: missing paper PDF for Evidence: {_evidence_address(parsed)}"]
    elif source == "inference":
        basis = parsed.get("basis")
        if not basis:
            return [f"{label}: missing inference basis for Evidence: {_evidence_address(parsed)}"]
    else:
        return [f"{label}: unsupported evidence source for Evidence: {_evidence_address(parsed)}"]
    return []


def _manifest_output_matches(output_record: dict, output_name: str) -> bool:
    candidates = [
        output_record.get("file_name"),
        output_record.get("name"),
        output_record.get("output"),
        output_record.get("markdown_path"),
        output_record.get("pdf_path"),
        output_record.get("path"),
    ]
    normalized = output_name.replace("\\", "/")
    return any(str(candidate or "").replace("\\", "/").endswith(normalized) for candidate in candidates)


def _validate_mineru_manifest_reference(paper_root: Path, label: str, parsed: dict[str, str]) -> list[str]:
    manifest_path = paper_root / "mineru" / "mineru-manifest.json"
    if not manifest_path.exists():
        return [f"{label}: missing MinerU manifest for Evidence: {_evidence_address(parsed)}"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"{label}: invalid MinerU manifest JSON for Evidence: {_evidence_address(parsed)}: {exc}"]
    if not isinstance(manifest, dict):
        return [f"{label}: MinerU manifest must be an object for Evidence: {_evidence_address(parsed)}"]

    field = parsed.get("field")
    output_name = parsed.get("output")
    if not field:
        return [f"{label}: missing MinerU manifest field for Evidence: {_evidence_address(parsed)}"]

    outputs = [item for item in manifest.get("outputs") or [] if isinstance(item, dict)]
    if output_name:
        matching_outputs = [item for item in outputs if _manifest_output_matches(item, output_name)]
        if not matching_outputs:
            return [f"{label}: missing MinerU manifest output for Evidence: {_evidence_address(parsed)}"]
        if not any(field in item for item in matching_outputs):
            return [f"{label}: missing MinerU manifest output field for Evidence: {_evidence_address(parsed)}"]
        return []

    if field in manifest or any(field in item for item in outputs):
        return []
    return [f"{label}: missing MinerU manifest field for Evidence: {_evidence_address(parsed)}"]


def validate_reader_evidence(paper_root: Path, evidence_docs: dict[str, str]) -> tuple[bool, list[str]]:
    addresses: list[tuple[str, str]] = []
    for doc_name, text in evidence_docs.items():
        addresses.extend((doc_name, address) for address in _evidence_addresses(text))
    if not addresses:
        return False, ["reader outputs missing structured Evidence lines"]

    metadata = json.loads((paper_root / "metadata.json").read_text(encoding="utf-8"))
    mineru_text = resolve_mineru_markdown_path(paper_root).read_text(encoding="utf-8")
    headings = _mineru_headings(mineru_text)
    failures: list[str] = []

    for doc_name, address in addresses:
        parsed = _parse_evidence_address(address)
        if not parsed:
            failures.append(f"{doc_name}: unsupported evidence address: {address}")
            continue
        failures.extend(_validate_evidence_reference(paper_root, doc_name, parsed, metadata, headings))

    if failures:
        return False, failures
    return True, [f"Validated {len(addresses)} structured reader evidence address(es)"]


def _expected_evidence_address(source: str, locator: dict) -> str | None:
    if not isinstance(locator, dict) or not locator:
        return None
    parts = [f"source={source}"]
    parts.extend(f"{key}={value}" for key, value in locator.items() if value)
    return "; ".join(parts)


def validate_evidence_map(paper_root: Path) -> tuple[bool, list[str]]:
    evidence_map_path = paper_root / "reader" / "evidence-map.json"
    if not evidence_map_path.exists():
        return False, ["reader/evidence-map.json missing"]

    metadata = json.loads((paper_root / "metadata.json").read_text(encoding="utf-8"))
    mineru_text = resolve_mineru_markdown_path(paper_root).read_text(encoding="utf-8")
    headings = _mineru_headings(mineru_text)
    failures: list[str] = []

    try:
        evidence_map = json.loads(evidence_map_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, [f"reader/evidence-map.json invalid JSON: {exc}"]

    if evidence_map.get("schema_version") != "epi-reader-evidence-map-v1":
        failures.append("reader/evidence-map.json unsupported schema_version")

    declared_roles = set(evidence_map.get("reader_roles", []))
    if not REQUIRED_READER_ROLES.issubset(declared_roles):
        missing = ", ".join(sorted(REQUIRED_READER_ROLES - declared_roles))
        failures.append(f"reader/evidence-map.json missing reader role declaration(s): {missing}")

    required_artifacts = evidence_map.get("required_artifacts", [])
    if required_artifacts is not None and not isinstance(required_artifacts, list):
        failures.append("reader/evidence-map.json required_artifacts must be a list")
        required_artifacts = []
    for artifact in required_artifacts:
        if not isinstance(artifact, str):
            failures.append("reader/evidence-map.json required_artifacts entries must be strings")
            continue
        if not artifact.startswith("reader/"):
            failures.append(f"reader/evidence-map.json required artifact must stay under reader/: {artifact}")
            continue
        if not (paper_root / artifact).exists():
            failures.append(f"reader/evidence-map.json required artifact missing: {artifact}")

    claims = evidence_map.get("claims")
    if not isinstance(claims, list) or not claims:
        failures.append("reader/evidence-map.json missing claims")
        claims = []

    seen_roles: set[str] = set()
    for index, claim in enumerate(claims, start=1):
        label = f"reader/evidence-map.json claim {index}"
        if not isinstance(claim, dict):
            failures.append(f"{label}: claim must be an object")
            continue
        for field in ("claim_id", "claim", "reader_role", "reader_artifact", "source", "locator", "evidence_address"):
            if not claim.get(field):
                failures.append(f"{label}: missing {field}")
        reader_role = claim.get("reader_role")
        if reader_role:
            seen_roles.add(str(reader_role))
            if reader_role not in REQUIRED_READER_ROLES:
                failures.append(f"{label}: unsupported reader_role={reader_role}")

        reader_artifact = claim.get("reader_artifact")
        if isinstance(reader_artifact, str):
            if not reader_artifact.startswith("reader/"):
                failures.append(f"{label}: reader_artifact must stay under reader/")
            elif not (paper_root / reader_artifact).exists():
                failures.append(f"{label}: reader_artifact missing: {reader_artifact}")

        source = claim.get("source")
        locator = claim.get("locator")
        evidence_address = claim.get("evidence_address")
        expected_address = _expected_evidence_address(str(source), locator)
        if expected_address is None:
            failures.append(f"{label}: locator must be a non-empty object")
            continue
        if evidence_address != expected_address:
            failures.append(f"{label}: evidence_address does not match source/locator")
            continue
        parsed = _parse_evidence_address(str(evidence_address))
        if not parsed:
            failures.append(f"{label}: unsupported evidence address: {evidence_address}")
            continue
        failures.extend(_validate_evidence_reference(paper_root, label, parsed, metadata, headings))

    if not REQUIRED_READER_ROLES.issubset(seen_roles):
        missing = ", ".join(sorted(REQUIRED_READER_ROLES - seen_roles))
        failures.append(f"reader/evidence-map.json missing claim(s) for reader role(s): {missing}")

    if failures:
        return False, failures
    return True, [f"Validated {len(claims)} evidence-map claim(s) across {len(seen_roles)} reader role(s)"]


def validate_claim_support_map(paper_root: Path, *, required: bool = False) -> tuple[bool, list[str]]:
    support_path = paper_root / "reader" / "claim-support.json"
    if not support_path.exists():
        if required:
            return False, ["reader/claim-support.json missing"]
        return True, ["reader/claim-support.json not present; using reader/evidence-map.json only"]

    try:
        support_map = json.loads(support_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return False, [f"reader/claim-support.json invalid JSON: {exc}"]

    failures: list[str] = []
    if support_map.get("schema_version") != "epi-claim-support-v1":
        failures.append("reader/claim-support.json unsupported schema_version")

    claims = support_map.get("claims")
    if not isinstance(claims, list) or not claims:
        failures.append("reader/claim-support.json missing claims")
        claims = []

    evidence_map_claims: dict[str, dict] = {}
    evidence_map_path = paper_root / "reader" / "evidence-map.json"
    if evidence_map_path.exists():
        try:
            evidence_map = json.loads(evidence_map_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            evidence_map = {}
        evidence_map_claims = {
            str(claim.get("claim_id")): claim
            for claim in evidence_map.get("claims", [])
            if isinstance(claim, dict) and claim.get("claim_id")
        }

    seen_statuses: set[str] = set()
    for index, claim in enumerate(claims, start=1):
        label = f"reader/claim-support.json claim {index}"
        if not isinstance(claim, dict):
            failures.append(f"{label}: claim must be an object")
            continue
        for field in (
            "claim_id",
            "claim",
            "reader_role",
            "reader_artifact",
            "source",
            "locator",
            "evidence_address",
            "support_status",
            "support_grade",
            "epistemic_status",
        ):
            if not claim.get(field):
                failures.append(f"{label}: missing {field}")
        source = str(claim.get("source") or "")
        expected_support = classify_claim_support(source)
        for field, expected in expected_support.items():
            if claim.get(field) != expected:
                failures.append(f"{label}: {field}={claim.get(field)} does not match source={source}")
        support_status = claim.get("support_status")
        if support_status:
            seen_statuses.add(str(support_status))
        claim_id = str(claim.get("claim_id") or "")
        evidence_claim = evidence_map_claims.get(claim_id)
        if evidence_claim:
            for field in ("claim", "reader_role", "reader_artifact", "source", "locator", "evidence_address"):
                if claim.get(field) != evidence_claim.get(field):
                    failures.append(f"{label}: {field} does not match reader/evidence-map.json")

    support_counts = support_map.get("support_counts")
    if not isinstance(support_counts, dict):
        failures.append("reader/claim-support.json support_counts must be an object")
    else:
        actual_counts = {status: sum(1 for claim in claims if isinstance(claim, dict) and claim.get("support_status") == status) for status in seen_statuses}
        for status, count in actual_counts.items():
            if support_counts.get(status) != count:
                failures.append(f"reader/claim-support.json support_counts[{status}] is stale")

    if failures:
        return False, failures
    return True, [f"Validated {len(claims)} claim-support record(s) across {len(seen_statuses)} support status(es)"]
