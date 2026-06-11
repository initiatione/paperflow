from __future__ import annotations

import re


_CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_FENCED_BLOCK_PATTERN = re.compile(r"```.*?```", re.DOTALL)
_EVIDENCE_ENTRY_SECTION_PATTERN = re.compile(
    r"(?ms)^##\s*原文与证据入口\s*$.*?(?=^##\s+|\Z)"
)


def strip_frontmatter(markdown: str) -> str:
    lines = markdown.splitlines()
    if not lines or lines[0].strip() != "---":
        return markdown
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[index + 1 :])
    return markdown


def body_language_signal(markdown: str) -> dict[str, object]:
    body = strip_frontmatter(markdown)
    body = _FENCED_BLOCK_PATTERN.sub("", body)
    body = _EVIDENCE_ENTRY_SECTION_PATTERN.sub("", body)
    cjk_count = len(_CJK_PATTERN.findall(body))
    return {
        "body_character_count": len(body.strip()),
        "cjk_character_count": cjk_count,
        "has_chinese_body": cjk_count >= 8,
    }


def formal_page_language_issues(markdown: str) -> list[str]:
    signal = body_language_signal(markdown)
    if signal["has_chinese_body"]:
        return []
    return [
        "formal page must follow Chinese-default body prose; English is allowed for paper titles, terms, abbreviations, evidence fields, paths, code, formulas, and metrics"
    ]


def final_source_review_language_policy() -> dict[str, object]:
    return {
        "body_default_language": "zh",
        "allowed_english": [
            "paper titles",
            "technical terms",
            "abbreviations",
            "evidence fields",
            "paths",
            "code",
            "formulas",
            "metrics",
        ],
        "worker_context_rule": (
            "Independent subtasks should run in fresh-context workers; main agents review final artifacts, "
            "changed file lists, and verification results instead of long intermediate transcripts."
        ),
    }


def language_policy_is_reviewed(section: dict[str, object]) -> bool:
    policy = section.get("language_policy") if isinstance(section.get("language_policy"), dict) else {}
    return (
        section.get("status") == "reviewed"
        and policy.get("body_default_language") == "zh"
        and policy.get("chinese_body_default") is True
    )
