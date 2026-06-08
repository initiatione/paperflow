from __future__ import annotations


READER_ROLES = [
    "nature-sci-editor",
    "peer-reviewer",
    "senior-domain-researcher",
]
REQUIRED_ARTIFACTS = [
    "reader/reader.md",
    "reader/editorial-summary.md",
    "reader/technical-reading.md",
    "reader/research-notes.md",
    "reader/figures.md",
    "reader/reproducibility.md",
    "reader/implementation-ideas.md",
    "reader/claim-support.json",
]


def markdown_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_heading = ""
    current_body: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            if current_heading and current_body:
                sections.append((current_heading, current_body[0]))
            current_heading = line.lstrip("#").strip()
            current_body = []
            continue
        current_body.append(line)

    if current_heading and current_body:
        sections.append((current_heading, current_body[0]))
    return sections


def evidence_line(source: str, key: str, value: str) -> str:
    return f"Evidence: source={source}; {key}={value}"


def evidence_address(source: str, locator: dict[str, str]) -> str:
    parts = [f"source={source}"]
    parts.extend(f"{key}={value}" for key, value in locator.items())
    return "; ".join(parts)


def claim_record(
    *,
    claim_id: str,
    reader_role: str,
    reader_artifact: str,
    claim: str,
    source: str,
    locator: dict[str, str],
) -> dict:
    return {
        "claim_id": claim_id,
        "reader_role": reader_role,
        "reader_artifact": reader_artifact,
        "claim": claim,
        "source": source,
        "locator": locator,
        "evidence_address": evidence_address(source, locator),
    }


def first_section(sections: list[tuple[str, str]], preferred_heading: str, fallback_index: int = 0) -> tuple[str, str]:
    for heading, body in sections:
        if heading.lower() == preferred_heading.lower():
            return heading, body
    if sections:
        return sections[min(fallback_index, len(sections) - 1)]
    return preferred_heading, "No parsed section text was available."
