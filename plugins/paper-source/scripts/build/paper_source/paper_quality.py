from __future__ import annotations

import json
import re
from pathlib import Path

from paper_source.artifacts import read_json_dict
from paper_source.source_artifacts import resolve_mineru_markdown_path


IDENTITY_FIELDS = (
    "doi",
    "arxiv_id",
    "arxiv",
    "arxiv_url",
    "url",
    "paper_url",
    "pdf_url",
    "source_url",
    "canonical_url",
    "venue",
)
URL_IDENTITY_FIELDS = {"url", "paper_url", "pdf_url", "source_url", "canonical_url", "arxiv_url"}
DOI_IDENTITY_FIELDS = {"doi"}
ARXIV_IDENTITY_FIELDS = {"arxiv_id", "arxiv"}
VENUE_IDENTITY_FIELDS = {"venue"}
PLACEHOLDER_VALUES = {"unknown", "not available", "n/a", "na", "none", "null", "-", "tbd"}

CLAIM_SUPPORT_RE = re.compile(
    r"\b(claim|core contribution|contribution|propose|proposes|present|presents|"
    r"performance|outperform|better|sota|state-of-the-art|generaliz|泛化|性能|贡献)\b",
    re.IGNORECASE,
)
PERFORMANCE_CLAIM_RE = re.compile(
    r"\b(outperform|outperforms|better|superior|sota|state-of-the-art|beats?|improv(?:e|es|ed|ement))\b",
    re.IGNORECASE,
)
BASELINE_RE = re.compile(
    r"\b(baselines?|compared with|compared to|comparison against|control group|ablation)\b",
    re.IGNORECASE,
)
METRIC_RE = re.compile(
    r"\b(metric|accuracy|success rate|reward|error|latency|throughput|f1|map|rmse|mae|auc|score)\b|%",
    re.IGNORECASE,
)
TASK_RE = re.compile(
    r"\b(dataset|benchmark|task|environment|simulator|experiment setup|evaluation setting|scenario)\b",
    re.IGNORECASE,
)
LIMITED_SCOPE_RE = re.compile(r"\b(simulat(?:ion|ed)|demo|small-scale|prototype|toy|lab|benchmark)\b", re.IGNORECASE)
OVERCLAIM_RE = re.compile(
    r"\b(real-world deployment|production|all robots|any task|universal|guarantee|general conclusion|"
    r"ready for real-world|deploy(?:ed|ment) across)\b",
    re.IGNORECASE,
)
PARSE_LIMITATION_RE = re.compile(
    r"(formula omitted|image omitted|missing figure|missing formula|parse failed|unresolved formula|"
    r"no figures were detected)",
    re.IGNORECASE,
)


def _metadata_values(metadata: dict, field: str) -> list[str]:
    value = metadata.get(field)
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _has_stable_identity_value(field: str, value: str) -> bool:
    normalized = value.strip().lower()
    if not normalized or normalized in PLACEHOLDER_VALUES:
        return False
    if field in URL_IDENTITY_FIELDS:
        return normalized.startswith(("http://", "https://")) or "doi.org/" in normalized or "arxiv.org/" in normalized
    if field in DOI_IDENTITY_FIELDS:
        return normalized.startswith(("10.", "doi:")) or "doi.org/" in normalized
    if field in ARXIV_IDENTITY_FIELDS:
        return bool(
            normalized.startswith("arxiv:")
            or "arxiv.org/" in normalized
            or re.match(r"^\d{4}\.\d{4,5}(v\d+)?$", normalized)
        )
    if field in VENUE_IDENTITY_FIELDS:
        return True
    if field == "id":
        return normalized.startswith(("10.", "doi:", "arxiv:")) or "doi.org/" in normalized or "arxiv.org/" in normalized
    return False


def _combine_reader_text(reader_text: str, additional_reader_texts: list[str] | tuple[str, ...] | None) -> str:
    texts = [reader_text, *(additional_reader_texts or [])]
    return "\n".join(text for text in texts if text)


def _reader_claim_blocks(reader_text: str) -> list[dict[str, object]]:
    blocks: list[dict[str, object]] = []
    current: dict[str, object] | None = None

    for line_number, raw_line in enumerate(reader_text.splitlines(), start=1):
        stripped = raw_line.strip()
        if stripped.startswith("- "):
            if current:
                blocks.append(current)
            current = {
                "line_number": line_number,
                "claim": stripped.removeprefix("- ").strip(),
                "lines": [stripped],
                "has_evidence": stripped.startswith("Evidence:"),
            }
            continue

        if current is None:
            continue
        if stripped.startswith("#"):
            blocks.append(current)
            current = None
            continue

        lines = current["lines"]
        assert isinstance(lines, list)
        lines.append(stripped)
        if stripped.startswith("Evidence:"):
            current["has_evidence"] = True

    if current:
        blocks.append(current)
    return blocks


def _local_regex_contexts(text: str, pattern: re.Pattern[str], *, window: int = 2) -> list[str]:
    contexts: list[str] = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not pattern.search(line):
            continue
        start = max(0, index - window)
        end = min(len(lines), index + window + 1)
        context = "\n".join(context_line for context_line in lines[start:end] if context_line.strip()).strip()
        if context:
            contexts.append(context)
    return contexts


def _check_paper_identity(metadata: dict, paper_pdf_exists: bool, metadata_exists: bool) -> dict:
    evidence: list[str] = []
    failures: list[str] = []
    title_values = _metadata_values(metadata, "title")
    stable_identity_values: list[str] = []
    for field in IDENTITY_FIELDS:
        stable_identity_values.extend(
            value for value in _metadata_values(metadata, field) if _has_stable_identity_value(field, value)
        )
    stable_identity_values.extend(
        value
        for value in _metadata_values(metadata, "id")
        if _has_stable_identity_value("id", value)
    )

    if not paper_pdf_exists:
        failures.append("paper_identity: paper.pdf missing")
    if not metadata_exists:
        failures.append("paper_identity: metadata.json missing")
    if not title_values:
        failures.append("paper_identity: missing title")
    if not stable_identity_values:
        failures.append("paper_identity: missing stable identifier such as URL, DOI, arXiv ID, or venue")

    if title_values:
        evidence.append("paper_identity: title present")
    if stable_identity_values:
        evidence.append("paper_identity: stable identifier present")

    return {
        "status": "fail" if failures else "pass",
        "evidence": evidence,
        "failures": failures,
        "warnings": [],
    }


def _check_claim_support(reader_text: str) -> dict:
    failures: list[str] = []
    supported_count = 0
    for block in _reader_claim_blocks(reader_text):
        claim = str(block["claim"])
        needs_support = bool(CLAIM_SUPPORT_RE.search(claim))
        if not needs_support:
            continue
        if block["has_evidence"]:
            supported_count += 1
            continue
        failures.append(f"claim_support: {claim.split(':', 1)[0]} lacks a local Evidence line")

    evidence = [f"claim_support: {supported_count} key reader claim(s) include local Evidence lines"]
    return {
        "status": "fail" if failures else "pass",
        "evidence": evidence,
        "failures": failures,
        "warnings": [],
    }


def _performance_claim_contexts(reader_text: str, mineru_text: str) -> list[str]:
    reader_contexts: list[str] = []
    for block in _reader_claim_blocks(reader_text):
        lines = block["lines"]
        assert isinstance(lines, list)
        block_text = "\n".join(str(line) for line in lines)
        if PERFORMANCE_CLAIM_RE.search(block_text):
            reader_contexts.append(block_text)

    if not reader_contexts:
        return []

    mineru_contexts = _local_regex_contexts(mineru_text, PERFORMANCE_CLAIM_RE)
    supplemental_context = "\n".join(mineru_contexts)
    return [
        "\n".join(context for context in [reader_context, supplemental_context] if context).strip()
        for reader_context in reader_contexts
    ]


def _check_benchmark_integrity(reader_text: str, mineru_text: str) -> dict:
    contexts = _performance_claim_contexts(reader_text, mineru_text)
    if not contexts:
        return {
            "status": "pass",
            "evidence": ["benchmark_integrity: no explicit outperform/SOTA claim detected"],
            "failures": [],
            "warnings": [],
        }

    missing: set[str] = set()
    for context in contexts:
        if not BASELINE_RE.search(context):
            missing.add("baseline")
        if not METRIC_RE.search(context):
            missing.add("metric")
        if not TASK_RE.search(context):
            missing.add("dataset/task or experiment setting")

    failures = [f"benchmark_integrity: performance claim missing {item}" for item in sorted(missing)]
    return {
        "status": "fail" if failures else "pass",
        "evidence": ["benchmark_integrity: performance claim includes baseline, metric, and task context"]
        if not failures
        else [],
        "failures": failures,
        "warnings": [],
    }


def _check_engineering_reproducibility(metadata: dict, *texts: str) -> dict:
    combined = "\n".join([json.dumps(metadata, ensure_ascii=False), *texts]).lower()
    required_terms = {
        "code": ("code", "github", "repository", "implementation"),
        "data": ("data", "dataset"),
        "model": ("model", "weights", "checkpoint"),
        "config": ("config", "hyperparameter", "parameter", "setting"),
        "simulator": ("simulator", "simulation", "gazebo", "isaac", "mujoco", "pybullet", "ros"),
        "hardware": ("hardware", "robot", "gpu", "sensor", "platform"),
    }
    missing = [
        category
        for category, terms in required_terms.items()
        if not any(term in combined for term in terms)
    ]
    warnings = []
    if missing:
        warnings.append("engineering_reproducibility: missing " + ", ".join(missing))
    return {
        "status": "warning" if missing else "pass",
        "evidence": ["engineering_reproducibility: code/data/model/config/simulator/hardware scanned"],
        "failures": [],
        "warnings": warnings,
    }


def _check_scope_overclaim(reader_text: str, mineru_text: str) -> dict:
    combined = f"{reader_text}\n{mineru_text}"
    failures: list[str] = []
    if LIMITED_SCOPE_RE.search(combined) and OVERCLAIM_RE.search(reader_text):
        failures.append(
            "scope_overclaim: limited simulation/demo/small-scale evidence is written as real deployment or universal conclusion"
        )
    return {
        "status": "fail" if failures else "pass",
        "evidence": ["scope_overclaim: no simulation/demo-to-real deployment overclaim detected"]
        if not failures
        else [],
        "failures": failures,
        "warnings": [],
    }


def _check_parse_vs_paper_failure(paper_pdf_exists: bool, mineru_text: str, figures_text: str) -> dict:
    warnings: list[str] = []
    if paper_pdf_exists and PARSE_LIMITATION_RE.search(f"{mineru_text}\n{figures_text}"):
        warnings.append(
            "parse_vs_paper_failure: MinerU parse limitation detected; inspect PDF before treating missing figures/formulas as absent from the paper"
        )
    return {
        "status": "warning" if warnings else "pass",
        "evidence": ["parse_vs_paper_failure: parse limitations scanned"],
        "failures": [],
        "warnings": warnings,
    }


def review_paper_quality(
    paper_root: Path,
    *,
    reader_text: str,
    additional_reader_texts: list[str] | tuple[str, ...] | None = None,
    figures_text: str,
    reproducibility_text: str,
) -> dict:
    metadata_path = paper_root / "metadata.json"
    mineru_path = resolve_mineru_markdown_path(paper_root)
    paper_pdf_exists = (paper_root / "paper.pdf").exists()
    metadata_exists = metadata_path.exists()
    metadata = read_json_dict(metadata_path, default={}) if metadata_exists else {}
    mineru_text = mineru_path.read_text(encoding="utf-8") if mineru_path.exists() else ""
    combined_reader_text = _combine_reader_text(reader_text, additional_reader_texts)

    checks = {
        "paper_identity": _check_paper_identity(metadata, paper_pdf_exists, metadata_exists),
        "claim_support": _check_claim_support(combined_reader_text),
        "benchmark_integrity": _check_benchmark_integrity(combined_reader_text, mineru_text),
        "engineering_reproducibility": _check_engineering_reproducibility(
            metadata,
            combined_reader_text,
            mineru_text,
            figures_text,
            reproducibility_text,
        ),
        "scope_overclaim": _check_scope_overclaim(combined_reader_text, mineru_text),
        "parse_vs_paper_failure": _check_parse_vs_paper_failure(paper_pdf_exists, mineru_text, figures_text),
    }
    failures = [failure for check in checks.values() for failure in check["failures"]]
    warnings = [warning for check in checks.values() for warning in check["warnings"]]
    evidence = [item for check in checks.values() for item in check["evidence"]]
    return {
        "passed": not failures,
        "checks": checks,
        "evidence": failures or evidence,
        "warnings": warnings,
    }
