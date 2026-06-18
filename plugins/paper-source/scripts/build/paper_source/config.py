from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from paper_source.artifacts import (
    paper_source_meta_root,
    read_json_dict,
    runs_root,
    utc_now,
    write_json_atomic,
    write_text_atomic,
)
from paper_source.config_protection import CONFIG_RESTORE_CONFIRMATION

BUILTIN_GROK_ACADEMIC_DOMAINS = [
    "ieeexplore.ieee.org",
    "dl.acm.org",
    "sciencedirect.com",
    "link.springer.com",
    "springer.com",
    "jstor.org",
    "webofscience.com",
    "scopus.com",
    "researchgate.net",
]


@dataclass(frozen=True)
class GrokAcademicDomainsConfig:
    mode: str
    domains: list[str]
    effective_domains: list[str]


@dataclass(frozen=True)
class GrokSearchConfig:
    mode: str
    targeted_query_budget: int
    parallel_query_budget: int
    grok_only_recommendation_cap: int
    academic_domains: GrokAcademicDomainsConfig


@dataclass(frozen=True)
class PipelineConfig:
    plugin_root: Path
    vault_path: Path
    runs_dir: Path
    max_results: int
    profile: str
    domains: list[str]
    positive_keywords: list[str]
    negative_keywords: list[str]
    venue_prior: list[str]
    paper_search_command: str | None
    paper_search_sources: list[str]
    easyscholar_enabled: bool
    easyscholar_timeout_seconds: int
    easyscholar_cache_ttl_days: int
    easyscholar_max_candidates_per_run: int
    grok_search: GrokSearchConfig
    quality_evidence_terms: object


@dataclass(frozen=True)
class PaperSourceConfigPaths:
    vault_path: Path
    meta_dir: Path
    config_path: Path
    state_path: Path
    history_dir: Path


DEFAULT_PAPER_SOURCE_CONFIG: dict[str, Any] = {
    "profile": "general_academic_research",
    "domains": [],
    "positive_keywords": [],
    "negative_keywords": [],
    "venue_prior": [],
    "budget": {"max_results": 20},
    "paper_search": {"command": "paper-search", "sources": ["arxiv", "semantic", "openalex", "crossref"]},
    "grok_search": {
        "mode": "targeted",
        "targeted_query_budget": 5,
        "parallel_query_budget": 8,
        "grok_only_recommendation_cap": 5,
        "academic_domains": {"mode": "append", "domains": []},
    },
    "quality_enrichment": {
        "easyscholar": {
            "enabled": True,
            "timeout_seconds": 15,
            "cache_ttl_days": 30,
            "max_candidates_per_run": 50,
        }
    },
    "ranking": {"quality_evidence_terms": {}},
    "mineru": {
        "token_source": "MINERU_TOKEN env",
        "command": "python skills/mineru-paper-parser/scripts/mineru_batch_to_md.py",
    },
    "zotero": {"enabled": False, "collection": "Paper Source"},
    "human_gate": {"mode": "before_promote"},
}

_FLAT_FIELD_PATHS: dict[str, tuple[str, ...]] = {
    "profile": ("profile",),
    "domains": ("domains",),
    "positive_keywords": ("positive_keywords",),
    "negative_keywords": ("negative_keywords",),
    "venue_prior": ("venue_prior",),
    "max_results": ("budget", "max_results"),
    "paper_search_command": ("paper_search", "command"),
    "paper_search_sources": ("paper_search", "sources"),
    "easyscholar_enabled": ("quality_enrichment", "easyscholar", "enabled"),
    "easyscholar_timeout_seconds": ("quality_enrichment", "easyscholar", "timeout_seconds"),
    "easyscholar_cache_ttl_days": ("quality_enrichment", "easyscholar", "cache_ttl_days"),
    "easyscholar_max_candidates_per_run": ("quality_enrichment", "easyscholar", "max_candidates_per_run"),
    "mineru_token_source": ("mineru", "token_source"),
    "mineru_command": ("mineru", "command"),
    "zotero_enabled": ("zotero", "enabled"),
    "zotero_collection": ("zotero", "collection"),
    "human_gate_mode": ("human_gate", "mode"),
}

_TOP_LEVEL_CONFIG_KEYS = {
    "profile",
    "domains",
    "positive_keywords",
    "negative_keywords",
    "venue_prior",
    "budget",
    "paper_search",
    "grok_search",
    "quality_enrichment",
    "ranking",
    "quality_evidence_terms",
    "mineru",
    "zotero",
    "human_gate",
}

_MISSING = object()


def config_paths(vault_path: Path) -> PaperSourceConfigPaths:
    vault_path = vault_path.resolve()
    meta_dir = paper_source_meta_root(vault_path)
    return PaperSourceConfigPaths(
        vault_path=vault_path,
        meta_dir=meta_dir,
        config_path=meta_dir / "paper-source-config.yaml",
        state_path=meta_dir / "paper-source-config-state.json",
        history_dir=meta_dir / "config-history",
    )


def _parse_yaml_scalar(raw: str) -> Any:
    raw = raw.strip()
    if raw.startswith('"') and raw.endswith('"'):
        return json.loads(raw)
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1]
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none", "~"}:
        return None
    if raw.startswith("[") or raw.startswith("{"):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    try:
        return int(raw)
    except ValueError:
        try:
            return float(raw)
        except ValueError:
            return raw


def _parse_simple_yaml_text(text: str) -> dict[str, Any]:
    lines: list[tuple[int, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped == "---" or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        lines.append((indent, stripped))

    index = 0

    def parse_mapping(expected_indent: int) -> dict[str, Any]:
        nonlocal index
        payload: dict[str, Any] = {}
        while index < len(lines):
            indent, stripped = lines[index]
            if indent < expected_indent:
                break
            if indent > expected_indent:
                raise ValueError(f"unsupported yaml indentation: {stripped}")
            if stripped.startswith("- "):
                raise ValueError(f"unexpected yaml list item: {stripped}")
            key, separator, value = stripped.partition(":")
            if not separator:
                raise ValueError(f"unsupported yaml line: {stripped}")
            key = key.strip()
            value = value.strip()
            index += 1
            if value:
                payload[key] = _parse_yaml_scalar(value)
                continue
            if index >= len(lines) or lines[index][0] <= indent:
                payload[key] = {}
                continue
            child_indent, child = lines[index]
            if child.startswith("- "):
                items: list[Any] = []
                while index < len(lines) and lines[index][0] == child_indent and lines[index][1].startswith("- "):
                    items.append(_parse_yaml_scalar(lines[index][1][2:].strip()))
                    index += 1
                payload[key] = items
                continue
            payload[key] = parse_mapping(child_indent)
        return payload

    return parse_mapping(lines[0][0]) if lines else {}


def _parse_simple_yaml(path: Path) -> dict[str, Any]:
    return _parse_simple_yaml_text(path.read_text(encoding="utf-8"))


def _dump_yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = "" if value is None else str(value)
    if not text:
        return '""'
    if any(ch.isspace() for ch in text) or any(ch in text for ch in ":#[]{}"):
        return json.dumps(text, ensure_ascii=False)
    return text


def _dump_simple_yaml_mapping(payload: dict[str, Any], *, indent: int = 0) -> list[str]:
    lines: list[str] = []
    prefix = " " * indent
    for key, value in payload.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.extend(_dump_simple_yaml_mapping(value, indent=indent + 2))
            continue
        if isinstance(value, list):
            lines.append(f"{prefix}{key}:")
            for item in value:
                lines.append(f"{prefix}  - {_dump_yaml_scalar(item)}")
            continue
        lines.append(f"{prefix}{key}: {_dump_yaml_scalar(value)}")
    return lines


def _dump_simple_yaml(payload: dict[str, Any]) -> str:
    return "\n".join(_dump_simple_yaml_mapping(payload)) + "\n"


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [value]


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on", "enabled"}
    return bool(value)


def _validate_choice(value: object, *, field: str, choices: set[str]) -> str:
    text = str(value).strip().lower()
    if text not in choices:
        raise ValueError(f"{field} must be one of {sorted(choices)}; got {value!r}")
    return text


def _validate_int_range(value: object, *, field: str, minimum: int, maximum: int) -> int:
    number = int(value)
    if number < minimum or number > maximum:
        raise ValueError(f"{field} must be between {minimum} and {maximum}; got {number}")
    return number


def _normalize_hostname(value: object) -> str:
    text = str(value or "").strip().lower()
    if "://" in text:
        text = text.split("://", 1)[1]
    text = text.split("/", 1)[0].strip().strip(".")
    return text


def _dedupe_domains(domains: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for domain in domains:
        normalized = _normalize_hostname(domain)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique


def _parse_grok_search_config(interests: dict[str, Any]) -> GrokSearchConfig:
    raw = interests.get("grok_search")
    raw = raw if isinstance(raw, dict) else {}
    domains_raw = raw.get("academic_domains")
    domains_raw = domains_raw if isinstance(domains_raw, dict) else {}
    domain_mode = _validate_choice(
        domains_raw.get("mode", "append"),
        field="grok_search.academic_domains.mode",
        choices={"append", "override"},
    )
    configured_domains = _dedupe_domains([str(domain) for domain in _as_list(domains_raw.get("domains"))])
    builtin_domains = list(BUILTIN_GROK_ACADEMIC_DOMAINS)
    effective_domains = (
        _dedupe_domains(configured_domains)
        if domain_mode == "override"
        else _dedupe_domains([*builtin_domains, *configured_domains])
    )
    return GrokSearchConfig(
        mode=_validate_choice(raw.get("mode", "targeted"), field="grok_search.mode", choices={"targeted", "parallel", "off"}),
        targeted_query_budget=_validate_int_range(
            raw.get("targeted_query_budget", 5),
            field="grok_search.targeted_query_budget",
            minimum=3,
            maximum=10,
        ),
        parallel_query_budget=_validate_int_range(
            raw.get("parallel_query_budget", 8),
            field="grok_search.parallel_query_budget",
            minimum=5,
            maximum=15,
        ),
        grok_only_recommendation_cap=_validate_int_range(
            raw.get("grok_only_recommendation_cap", 5),
            field="grok_search.grok_only_recommendation_cap",
            minimum=0,
            maximum=5,
        ),
        academic_domains=GrokAcademicDomainsConfig(
            mode=domain_mode,
            domains=configured_domains,
            effective_domains=effective_domains,
        ),
    )


def _normalize_flat_value(key: str, value: Any) -> Any:
    if key in {"domains", "positive_keywords", "negative_keywords", "venue_prior", "paper_search_sources"}:
        return _as_list(value)
    if key in {
        "max_results",
        "easyscholar_timeout_seconds",
        "easyscholar_cache_ttl_days",
        "easyscholar_max_candidates_per_run",
    }:
        return int(value)
    if key in {"zotero_enabled", "easyscholar_enabled"}:
        return _as_bool(value)
    return value


def _set_path(payload: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    node = payload
    for key in path[:-1]:
        child = node.get(key)
        if not isinstance(child, dict):
            child = {}
            node[key] = child
        node = child
    node[path[-1]] = value


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
            continue
        base[key] = copy.deepcopy(value)
    return base


def _normalize_payload_to_config(payload: dict[str, Any], *, base: dict[str, Any] | None = None) -> dict[str, Any]:
    config = copy.deepcopy(base if base is not None else DEFAULT_PAPER_SOURCE_CONFIG)
    for key, value in payload.items():
        if key in _FLAT_FIELD_PATHS:
            _set_path(config, _FLAT_FIELD_PATHS[key], _normalize_flat_value(key, value))
            continue
        if "." in key:
            _set_path(config, tuple(part for part in key.split(".") if part), value)
            continue
        if key in _TOP_LEVEL_CONFIG_KEYS:
            if isinstance(value, dict) and isinstance(config.get(key), dict):
                _deep_merge(config[key], value)
            else:
                config[key] = copy.deepcopy(value)
    return config


def _flatten(payload: dict[str, Any], *, prefix: str = "") -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, value in payload.items():
        dotted = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flattened.update(_flatten(value, prefix=dotted))
            continue
        flattened[dotted] = value
    return flattened


def _format_diff_value(value: Any) -> str:
    if value == _MISSING:
        return "<missing>"
    if isinstance(value, list):
        return "[" + ", ".join(str(item) for item in value) + "]"
    return str(value)


def _config_diff(before: dict[str, Any], after: dict[str, Any]) -> str:
    before_flat = _flatten(before)
    after_flat = _flatten(after)
    lines: list[str] = []
    for key in sorted(set(before_flat) | set(after_flat)):
        before_value = before_flat.get(key, _MISSING)
        after_value = after_flat.get(key, _MISSING)
        if before_value != after_value:
            lines.append(f"{key}: {_format_diff_value(before_value)} -> {_format_diff_value(after_value)}")
    return "\n".join(lines)


def _history_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _unique_history_path(paths: PaperSourceConfigPaths, action: str) -> Path:
    paths.history_dir.mkdir(parents=True, exist_ok=True)
    base_name = f"{_history_timestamp()}-{action}.yaml"
    candidate = paths.history_dir / base_name
    counter = 1
    while candidate.exists():
        candidate = paths.history_dir / base_name.replace(".yaml", f"-{counter}.yaml")
        counter += 1
    return candidate


def _write_history_snapshot(paths: PaperSourceConfigPaths, content: str, *, action: str) -> Path:
    history_path = _unique_history_path(paths, action)
    write_text_atomic(history_path, content)
    return history_path


def load_wiki_config(vault_path: Path) -> dict[str, Any] | None:
    paths = config_paths(vault_path)
    if paths.config_path.exists():
        return _parse_simple_yaml(paths.config_path)
    return None


def config_status(vault_path: Path) -> dict[str, Any]:
    paths = config_paths(vault_path)
    state: dict[str, Any] = {}
    if paths.state_path.exists():
        state = read_json_dict(paths.state_path, default={}) or {}
    configured = paths.config_path.exists() and state.get("configured", True) is not False
    return {
        "configured": configured,
        "needs_onboarding": not configured,
        "config_path": str(paths.config_path),
        "state_path": str(paths.state_path),
        "history_dir": str(paths.history_dir),
        "state": state,
    }


def init_config(vault_path: Path, answers: dict[str, Any]) -> dict[str, Any]:
    paths = config_paths(vault_path)
    config = _normalize_payload_to_config(answers)
    content = _dump_simple_yaml(config)
    paths.meta_dir.mkdir(parents=True, exist_ok=True)
    write_text_atomic(paths.config_path, content)
    history_path = _write_history_snapshot(paths, content, action="init-config")
    state = {
        "configured": True,
        "config_path": str(paths.config_path),
        "last_action": "init-config",
        "configured_by": str(answers.get("configured_by", "unknown")),
        "updated_at": utc_now(),
        "history_path": str(history_path),
    }
    write_json_atomic(paths.state_path, state)
    return {
        "status": "initialized",
        "config_path": str(paths.config_path),
        "state_path": str(paths.state_path),
        "history_path": str(history_path),
        "config": config,
    }


def _target_config_for_proposal(current: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    if proposal.get("mode") == "reset":
        config_payload = proposal.get("config")
        if not isinstance(config_payload, dict):
            raise ValueError("reset proposals require a config object")
        return _normalize_payload_to_config(config_payload)
    changes = proposal.get("changes")
    if not isinstance(changes, dict):
        raise ValueError("config update proposals require a changes object")
    return _normalize_payload_to_config(changes, base=current)


def propose_config_update(vault_path: Path, proposal: dict[str, Any]) -> dict[str, Any]:
    current = load_wiki_config(vault_path)
    if current is None:
        raise FileNotFoundError(f"missing Paper Source config: {config_paths(vault_path).config_path}")
    target = _target_config_for_proposal(current, proposal)
    paths = config_paths(vault_path)
    return {
        "status": "proposal",
        "mode": proposal.get("mode", "update"),
        "reason": proposal.get("reason", ""),
        "config_path": str(paths.config_path),
        "diff": _config_diff(current, target),
        "current": current,
        "proposed": target,
        "requires_confirmation": True,
    }


def apply_config_update(vault_path: Path, proposal: dict[str, Any], *, confirmed_by: str) -> dict[str, Any]:
    paths = config_paths(vault_path)
    current = load_wiki_config(vault_path)
    if current is None:
        current = copy.deepcopy(DEFAULT_PAPER_SOURCE_CONFIG)
        old_content = ""
    else:
        old_content = paths.config_path.read_text(encoding="utf-8")
    target = _target_config_for_proposal(current, proposal)
    diff = _config_diff(current, target)
    history_path = None
    if old_content:
        history_path = _write_history_snapshot(paths, old_content, action="apply-config-update")
    content = _dump_simple_yaml(target)
    write_text_atomic(paths.config_path, content)
    if history_path is None:
        history_path = _write_history_snapshot(paths, content, action="apply-config-update")
    state = {
        "configured": True,
        "config_path": str(paths.config_path),
        "last_action": "apply-config-update",
        "configured_by": confirmed_by,
        "updated_at": utc_now(),
        "history_path": str(history_path),
        "mode": proposal.get("mode", "update"),
    }
    write_json_atomic(paths.state_path, state)
    return {
        "status": "applied",
        "config_updated": True,
        "config_path": str(paths.config_path),
        "state_path": str(paths.state_path),
        "history_path": str(history_path),
        "diff": diff,
        "config": target,
    }


def _config_candidate_summary(path: Path, *, source_type: str, priority: int) -> dict[str, Any]:
    try:
        config = _parse_simple_yaml(path)
    except Exception as exc:
        return {
            "path": str(path),
            "status": "unreadable",
            "source_type": source_type,
            "priority": priority,
            "error": str(exc),
        }
    stat = path.stat()
    return {
        "path": str(path),
        "status": "readable",
        "source_type": source_type,
        "priority": priority,
        "updated_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "profile": config.get("profile"),
        "domains": config.get("domains", []),
        "max_results": config.get("budget", {}).get("max_results") if isinstance(config.get("budget"), dict) else None,
        "paper_search_sources": config.get("paper_search", {}).get("sources")
        if isinstance(config.get("paper_search"), dict)
        else None,
    }


def recover_config_candidates(vault_path: Path, *, backup_root: Path | None = None) -> dict[str, Any]:
    paths = config_paths(vault_path)
    search_roots = [
        ("current", 0, paths.config_path),
        ("config-history", 10, paths.history_dir),
    ]
    if backup_root is not None:
        search_roots.append(("provided-backup-root", 30, backup_root))
    else:
        search_roots.append(("reset-backups", 30, paths.vault_path.parent / "paper-research-wiki-reset-backups"))

    seen: set[Path] = set()
    candidates: list[dict[str, Any]] = []
    for source_type, priority, root in search_roots:
        root = root.resolve()
        if not root.exists():
            continue
        paths_to_check = [root] if root.is_file() else sorted(root.rglob("*.yaml"))
        for candidate_path in paths_to_check:
            resolved = candidate_path.resolve()
            if resolved in seen:
                continue
            if resolved.name == "epi-config.yaml" or "epi-config-history" in resolved.parts:
                continue
            if not resolved.name.endswith(".yaml"):
                continue
            seen.add(resolved)
            summary = _config_candidate_summary(resolved, source_type=source_type, priority=priority)
            if summary["status"] == "readable":
                candidates.append(summary)

    candidates.sort(key=lambda item: (int(item["priority"]), str(item.get("updated_at", ""))), reverse=True)
    candidates.sort(key=lambda item: int(item["priority"]))
    return {
        "status": "ok",
        "configured": paths.config_path.exists(),
        "config_path": str(paths.config_path),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


def restore_config_from_file(vault_path: Path, source_path: Path, *, confirmed_by: str) -> dict[str, Any]:
    if confirmed_by != CONFIG_RESTORE_CONFIRMATION:
        raise ValueError(f"config restore requires confirmed_by='{CONFIG_RESTORE_CONFIRMATION}'")
    paths = config_paths(vault_path)
    source_path = source_path.resolve()
    if not source_path.exists() or not source_path.is_file():
        raise FileNotFoundError(f"missing config restore source: {source_path}")
    restored_config = _parse_simple_yaml(source_path)
    content = _dump_simple_yaml(_normalize_payload_to_config(restored_config))

    paths.meta_dir.mkdir(parents=True, exist_ok=True)
    previous_history_path = None
    if paths.config_path.exists():
        previous_history_path = _write_history_snapshot(
            paths,
            paths.config_path.read_text(encoding="utf-8"),
            action="pre-config-restore",
        )
    write_text_atomic(paths.config_path, content)
    restored_history_path = _write_history_snapshot(paths, content, action="config-restore")
    state = {
        "configured": True,
        "config_path": str(paths.config_path),
        "last_action": "config-restore",
        "configured_by": confirmed_by,
        "updated_at": utc_now(),
        "history_path": str(restored_history_path),
        "restored_from": str(source_path),
    }
    if previous_history_path is not None:
        state["previous_history_path"] = str(previous_history_path)
    write_json_atomic(paths.state_path, state)
    return {
        "status": "restored",
        "config_path": str(paths.config_path),
        "state_path": str(paths.state_path),
        "history_path": str(restored_history_path),
        "restored_from": str(source_path),
        "previous_history_path": str(previous_history_path) if previous_history_path else None,
        "config": _parse_simple_yaml_text(content),
    }


def load_config(plugin_root: Path, vault_path: Path, max_results: int | None) -> PipelineConfig:
    plugin_root = plugin_root.resolve()
    vault_path = vault_path.resolve()
    interests = load_wiki_config(vault_path)
    if interests is None:
        interests_path = plugin_root / "templates" / "interests.example.yaml"
        interests = _parse_simple_yaml(interests_path) if interests_path.exists() else {}
    budget = interests.get("budget", {})
    configured_max = int(budget.get("max_results", 20))
    paper_search = interests.get("paper_search") if isinstance(interests.get("paper_search"), dict) else {}
    paper_search_command = paper_search.get("command")
    paper_search_sources = [str(source) for source in _as_list(paper_search.get("sources"))] or [
        "arxiv",
        "semantic",
        "openalex",
        "crossref",
    ]
    quality_enrichment = interests.get("quality_enrichment")
    if not isinstance(quality_enrichment, dict):
        quality_enrichment = {}
    easyscholar = quality_enrichment.get("easyscholar")
    if not isinstance(easyscholar, dict):
        easyscholar = {}
    grok_search = _parse_grok_search_config(interests)
    ranking = interests.get("ranking") if isinstance(interests.get("ranking"), dict) else {}
    quality_evidence_terms = ranking.get("quality_evidence_terms")
    if quality_evidence_terms is None:
        quality_evidence_terms = interests.get("quality_evidence_terms", {})
    return PipelineConfig(
        plugin_root=plugin_root,
        vault_path=vault_path,
        runs_dir=runs_root(vault_path),
        max_results=max_results if max_results is not None else configured_max,
        profile=str(interests.get("profile", "general_academic_research")),
        domains=[str(domain) for domain in _as_list(interests.get("domains"))],
        positive_keywords=list(interests.get("positive_keywords") or []),
        negative_keywords=list(interests.get("negative_keywords") or []),
        venue_prior=[str(venue) for venue in _as_list(interests.get("venue_prior"))],
        paper_search_command=str(paper_search_command) if paper_search_command else None,
        paper_search_sources=paper_search_sources,
        easyscholar_enabled=_as_bool(easyscholar.get("enabled", True)),
        easyscholar_timeout_seconds=int(easyscholar.get("timeout_seconds", 15)),
        easyscholar_cache_ttl_days=int(easyscholar.get("cache_ttl_days", 30)),
        easyscholar_max_candidates_per_run=int(easyscholar.get("max_candidates_per_run", 50)),
        grok_search=grok_search,
        quality_evidence_terms=quality_evidence_terms if isinstance(quality_evidence_terms, (dict, list)) else {},
    )
