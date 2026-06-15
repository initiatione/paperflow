from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Any

from paper_source.artifacts import paper_source_root, read_json_dict, utc_now, write_json_atomic


EASYSCHOLAR_API_BASE = "https://www.easyscholar.cc/open"
EASYSCHOLAR_CACHE_SCHEMA = "paper-source-easyscholar-cache-v1"
EASYSCHOLAR_RECORD_SCHEMA = "paper-source-easyscholar-record-v1"
DEFAULT_TIMEOUT_SECONDS = 15
DEFAULT_CACHE_TTL_DAYS = 30
DEFAULT_MAX_CANDIDATES_PER_RUN = 50
EASYSCHOLAR_STATUSES = (
    "matched",
    "disabled",
    "missing_key",
    "no_publication_name",
    "no_match",
    "cache_hit",
    "api_error",
    "timeout",
    "invalid_response",
)

EasyScholarClient = Callable[[str, str, int], dict[str, Any]]

_PUNCTUATION_RE = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class EasyScholarConfig:
    vault_path: Path
    enabled: bool = True
    secret_key: str | None = None
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    cache_ttl_days: int = DEFAULT_CACHE_TTL_DAYS
    max_candidates_per_run: int = DEFAULT_MAX_CANDIDATES_PER_RUN
    client: EasyScholarClient | None = None


def normalize_publication_name(publication_name: str) -> str:
    text = _PUNCTUATION_RE.sub(" ", str(publication_name or "").strip().lower())
    return _SPACE_RE.sub(" ", text).strip()


def cache_key_for_publication(publication_name: str) -> str:
    normalized = normalize_publication_name(publication_name)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]
    return f"{digest}.json"


def _rank_blocks(payload: dict) -> tuple[dict, dict]:
    data = payload.get("data") if isinstance(payload, dict) else None
    official_rank = data.get("officialRank") if isinstance(data, dict) else None
    if not isinstance(official_rank, dict):
        return {}, {}
    select_rank = official_rank.get("select")
    all_rank = official_rank.get("all")
    return (
        select_rank if isinstance(select_rank, dict) else {},
        all_rank if isinstance(all_rank, dict) else {},
    )


def _first_present(*values: object) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def parse_easyscholar_response(publication_name: str, payload: dict) -> dict:
    if not isinstance(payload, dict):
        return {
            "status": "invalid_response",
            "publication_name": publication_name,
            "source": "easyscholar",
            "metrics": {},
            "warnings": ["invalid_response"],
        }
    if payload.get("code") != 200 or not payload.get("data"):
        return {
            "status": "api_error",
            "publication_name": publication_name,
            "source": "easyscholar",
            "metrics": {},
            "warnings": [str(payload.get("msg") or "api_error")],
        }

    select_rank, all_rank = _rank_blocks(payload)
    field_map = {
        "jcr_quartile": _first_present(select_rank.get("sci")),
        "cas_zone_basic": _first_present(select_rank.get("sciBase")),
        "cas_zone_upgraded": _first_present(select_rank.get("sciUp")),
        "cas_top": _first_present(select_rank.get("sciUpTop")),
        "impact_factor": _first_present(all_rank.get("sciif")),
        "five_year_impact_factor": _first_present(select_rank.get("sciif5")),
        "jci": _first_present(all_rank.get("jci")),
        "esi_subject": _first_present(all_rank.get("esi")),
        "ei": _first_present(all_rank.get("eii")),
        "cas_warning": _first_present(all_rank.get("sciWarning")),
        "ccf": _first_present(all_rank.get("ccf")),
        "ccf_journal": _first_present(all_rank.get("ccfJournal")),
        "ccf_conference": _first_present(all_rank.get("ccfConference")),
        "abdc": _first_present(all_rank.get("abdc")),
        "ajg": _first_present(all_rank.get("ajg")),
        "ft50": _first_present(all_rank.get("ft50")),
        "utd24": _first_present(all_rank.get("utd24")),
        "fms": _first_present(all_rank.get("fms")),
        "pku_core": _first_present(all_rank.get("pku")),
        "cssci": _first_present(all_rank.get("cssci")),
        "cscd": _first_present(all_rank.get("cscd")),
    }
    metrics = {key: value for key, value in field_map.items() if value not in {None, ""}}
    if not metrics:
        return {
            "status": "no_match",
            "publication_name": publication_name,
            "source": "easyscholar",
            "metrics": {},
            "warnings": ["no_ranking_data"],
        }
    return {
        "status": "matched",
        "publication_name": publication_name,
        "source": "easyscholar",
        "metrics": metrics,
        "warnings": [],
    }


def _rank_letter_score(value: object, mapping: dict[str, float]) -> tuple[float, str | None]:
    text = str(value or "").strip()
    if not text:
        return 0.0, None
    normalized = text.upper().replace("级", "").replace("区", "").strip()
    if normalized in mapping:
        return mapping[normalized], text
    return 0.0, None


def _float_value(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def score_easyscholar_metrics(metrics: dict) -> dict:
    evidence: list[str] = []
    cautions: list[str] = []
    score = 0.0

    jcr_score, jcr_value = _rank_letter_score(
        metrics.get("jcr_quartile"),
        {"Q1": 0.40, "1": 0.40, "Q2": 0.26, "2": 0.26, "Q3": 0.12, "3": 0.12, "Q4": 0.05, "4": 0.05},
    )
    if jcr_value:
        score += jcr_score
        evidence.append(f"JCR {jcr_value}")

    cas_value = metrics.get("cas_zone_upgraded") or metrics.get("cas_zone_basic")
    cas_score, cas_label = _rank_letter_score(
        cas_value,
        {"1": 0.28, "2": 0.18, "3": 0.08, "4": 0.03, "TOP": 0.22},
    )
    if cas_label:
        score += cas_score
        evidence.append(f"CAS {cas_label}")
    if str(metrics.get("cas_top") or "").strip().lower() in {"top", "yes", "true", "1"}:
        score += 0.08
        evidence.append("CAS TOP")

    ccf_value = metrics.get("ccf") or metrics.get("ccf_conference") or metrics.get("ccf_journal")
    ccf_score, ccf_label = _rank_letter_score(ccf_value, {"A": 0.20, "B": 0.12, "C": 0.05})
    if ccf_label:
        score += ccf_score
        evidence.append(f"CCF {ccf_label}")

    abdc_score, abdc_label = _rank_letter_score(
        metrics.get("abdc"),
        {"A*": 0.22, "A": 0.18, "B": 0.10, "C": 0.04},
    )
    if abdc_label:
        score += abdc_score
        evidence.append(f"ABDC {abdc_label}")

    ajg_score, ajg_label = _rank_letter_score(
        metrics.get("ajg"),
        {"4*": 0.22, "4": 0.18, "3": 0.10, "2": 0.04, "1": 0.02},
    )
    if ajg_label:
        score += ajg_score
        evidence.append(f"AJG {ajg_label}")

    impact_factor = _float_value(metrics.get("impact_factor"))
    if impact_factor is not None:
        if impact_factor >= 10:
            score += 0.18
        elif impact_factor >= 5:
            score += 0.12
        elif impact_factor >= 2:
            score += 0.06
        evidence.append(f"impact_factor:{impact_factor:g}")

    for key, label in (
        ("ft50", "FT50"),
        ("utd24", "UTD24"),
        ("ei", "EI"),
        ("cssci", "CSSCI"),
        ("pku_core", "PKU Core"),
        ("cscd", "CSCD"),
    ):
        value = str(metrics.get(key) or "").strip().lower()
        if value in {"yes", "true", "1", "y", "是"}:
            score += 0.05
            evidence.append(label)

    if metrics.get("cas_warning"):
        cautions.append("cas_warning")
        score -= 0.20

    return {
        "score": round(max(0.0, min(1.0, score)), 4),
        "evidence": evidence,
        "cautions": cautions,
    }


def _raw_extra(raw_record: dict) -> dict:
    extra = raw_record.get("extra")
    if isinstance(extra, dict):
        return extra
    if isinstance(extra, str):
        try:
            parsed = json.loads(extra)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def publication_name_for_candidate(candidate: dict) -> str | None:
    for key in ("venue", "journal", "conference", "publication_venue", "container_title"):
        value = candidate.get(key)
        if str(value or "").strip():
            return str(value).strip()

    for raw_record in candidate.get("raw_records") or []:
        if not isinstance(raw_record, dict):
            continue
        extra = _raw_extra(raw_record)
        for source in (raw_record, extra):
            for key in ("publication_venue", "journal", "conference", "container_title", "venue"):
                value = source.get(key)
                if str(value or "").strip():
                    return str(value).strip()
    return None


def _cache_root(vault_path: Path) -> Path:
    return paper_source_root(vault_path) / "cache" / "easyscholar"


def _parse_dt(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _load_cache(path: Path) -> dict | None:
    payload = read_json_dict(path, default=None)
    if payload is None:
        return None
    if payload.get("schema_version") != EASYSCHOLAR_CACHE_SCHEMA:
        return None
    expires_at = _parse_dt(payload.get("expires_at"))
    if expires_at and expires_at < datetime.now(timezone.utc):
        return None
    return payload


def _write_cache(
    path: Path,
    *,
    publication_name: str,
    raw_response: dict,
    parsed_metrics: dict,
    status: str,
    ttl_days: int,
    error: str | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    queried_at = datetime.now(timezone.utc)
    payload = {
        "schema_version": EASYSCHOLAR_CACHE_SCHEMA,
        "publication_name": publication_name,
        "normalized_publication_name": normalize_publication_name(publication_name),
        "queried_at": queried_at.isoformat(),
        "expires_at": (queried_at + timedelta(days=ttl_days)).isoformat(),
        "status": status,
        "raw_response": raw_response,
        "parsed_metrics": parsed_metrics,
        "error": error,
    }
    write_json_atomic(path, payload)


def _default_client(publication_name: str, secret_key: str, timeout_seconds: int) -> dict:
    query = urllib.parse.urlencode({"secretKey": secret_key, "publicationName": publication_name})
    url = f"{EASYSCHOLAR_API_BASE}/getPublicationRank?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": "Paper Source EasyScholar Enricher"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _redact_secret(text: str, secret_key: str | None) -> str:
    redacted = re.sub(r"(secretKey=)[^&\s]+", lambda match: match.group(1) + "<redacted>", text)
    if not secret_key:
        return redacted
    for value in {
        secret_key,
        urllib.parse.quote(secret_key, safe=""),
        urllib.parse.quote_plus(secret_key),
    }:
        if value:
            redacted = redacted.replace(value, "<redacted>")
    return redacted


def _empty_metrics(status: str, publication_name: str | None, warning: str | None = None) -> dict:
    warnings = [warning] if warning else []
    return {
        "status": status,
        "publication_name": publication_name,
        "source": "easyscholar",
        "metrics": {},
        "warnings": warnings,
    }


def _record_item(
    *,
    candidate: dict,
    publication_name: str | None,
    status: str,
    cache_path: Path | None = None,
    error: str | None = None,
) -> dict:
    item = {
        "slug": candidate.get("slug"),
        "title": candidate.get("title"),
        "publication_name": publication_name,
        "status": status,
    }
    if cache_path is not None:
        item["cache_path"] = str(cache_path)
    if error:
        item["error"] = error
    return item


def _attach(candidate: dict, *, parsed_metrics: dict, signal: dict, status: str) -> dict:
    enriched = dict(candidate)
    verified_metrics = dict(enriched.get("verified_metrics") or {})
    verified_metrics["easyscholar"] = parsed_metrics
    quality_signals = dict(enriched.get("quality_signals") or {})
    quality_signals["easyscholar"] = signal
    enriched["verified_metrics"] = verified_metrics
    enriched["quality_signals"] = quality_signals
    enriched["easyscholar_status"] = status
    return enriched


def _summary(items: list[dict]) -> dict[str, int]:
    summary: dict[str, int] = {status: 0 for status in EASYSCHOLAR_STATUSES}
    for item in items:
        status = str(item.get("status") or "unknown")
        summary[status] = summary.get(status, 0) + 1
    return summary


def enrich_candidates_with_easyscholar(
    candidates: list[dict],
    config: EasyScholarConfig,
) -> tuple[list[dict], dict]:
    client = config.client or _default_client
    cache_root = _cache_root(config.vault_path)
    cache_root.mkdir(parents=True, exist_ok=True)
    enriched_candidates: list[dict] = []
    items: list[dict] = []
    processed = 0

    for candidate in candidates:
        publication_name = publication_name_for_candidate(candidate)
        if not config.enabled:
            parsed = _empty_metrics("disabled", publication_name)
            signal = score_easyscholar_metrics({})
            enriched_candidates.append(_attach(candidate, parsed_metrics=parsed, signal=signal, status="disabled"))
            items.append(_record_item(candidate=candidate, publication_name=publication_name, status="disabled"))
            continue
        if not publication_name:
            parsed = _empty_metrics("no_publication_name", None)
            signal = score_easyscholar_metrics({})
            enriched_candidates.append(
                _attach(candidate, parsed_metrics=parsed, signal=signal, status="no_publication_name")
            )
            items.append(_record_item(candidate=candidate, publication_name=None, status="no_publication_name"))
            continue
        if processed >= config.max_candidates_per_run:
            parsed = _empty_metrics("disabled", publication_name, "max_candidates_per_run_reached")
            signal = score_easyscholar_metrics({})
            enriched_candidates.append(_attach(candidate, parsed_metrics=parsed, signal=signal, status="disabled"))
            items.append(_record_item(candidate=candidate, publication_name=publication_name, status="disabled"))
            continue

        cache_path = cache_root / cache_key_for_publication(publication_name)
        cached = _load_cache(cache_path)
        if cached is not None:
            parsed = cached.get("parsed_metrics") or _empty_metrics(str(cached.get("status")), publication_name)
            signal = score_easyscholar_metrics(parsed.get("metrics") or {})
            enriched_candidates.append(_attach(candidate, parsed_metrics=parsed, signal=signal, status="cache_hit"))
            items.append(
                _record_item(
                    candidate=candidate,
                    publication_name=publication_name,
                    status="cache_hit",
                    cache_path=cache_path,
                )
            )
            continue

        if not config.secret_key:
            parsed = _empty_metrics("missing_key", publication_name)
            signal = score_easyscholar_metrics({})
            enriched_candidates.append(_attach(candidate, parsed_metrics=parsed, signal=signal, status="missing_key"))
            items.append(_record_item(candidate=candidate, publication_name=publication_name, status="missing_key"))
            continue

        processed += 1
        try:
            raw_response = client(publication_name, config.secret_key, config.timeout_seconds)
        except TimeoutError as exc:
            error = _redact_secret(str(exc), config.secret_key)
            parsed = _empty_metrics("timeout", publication_name, error)
            signal = score_easyscholar_metrics({})
            enriched_candidates.append(_attach(candidate, parsed_metrics=parsed, signal=signal, status="timeout"))
            items.append(
                _record_item(candidate=candidate, publication_name=publication_name, status="timeout", error=error)
            )
            _write_cache(
                cache_path,
                publication_name=publication_name,
                raw_response={},
                parsed_metrics=parsed,
                status="timeout",
                ttl_days=config.cache_ttl_days,
                error=error,
            )
        except (urllib.error.URLError, OSError, RuntimeError, ValueError) as exc:
            error = _redact_secret(str(exc), config.secret_key)
            parsed = _empty_metrics("api_error", publication_name, error)
            signal = score_easyscholar_metrics({})
            enriched_candidates.append(_attach(candidate, parsed_metrics=parsed, signal=signal, status="api_error"))
            items.append(
                _record_item(candidate=candidate, publication_name=publication_name, status="api_error", error=error)
            )
            _write_cache(
                cache_path,
                publication_name=publication_name,
                raw_response={},
                parsed_metrics=parsed,
                status="api_error",
                ttl_days=config.cache_ttl_days,
                error=error,
            )
        else:
            parsed = parse_easyscholar_response(publication_name, raw_response)
            status = parsed["status"]
            signal = score_easyscholar_metrics(parsed.get("metrics") or {})
            enriched_candidates.append(_attach(candidate, parsed_metrics=parsed, signal=signal, status=status))
            items.append(
                _record_item(candidate=candidate, publication_name=publication_name, status=status, cache_path=cache_path)
            )
            _write_cache(
                cache_path,
                publication_name=publication_name,
                raw_response=raw_response,
                parsed_metrics=parsed,
                status=status,
                ttl_days=config.cache_ttl_days,
            )

    record = {
        "schema_version": EASYSCHOLAR_RECORD_SCHEMA,
        "enabled": config.enabled,
        "started_at": utc_now(),
        "finished_at": utc_now(),
        "cache_root": str(cache_root),
        "candidate_count": len(candidates),
        "summary": _summary(items),
        "items": items,
        "upstream": {
            "package": "chaosman42/easyscholar-mcp",
            "api_base": EASYSCHOLAR_API_BASE,
            "endpoint": "/getPublicationRank",
        },
    }
    return enriched_candidates, record


def config_from_environment(
    vault_path: Path,
    *,
    enabled: bool = True,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    cache_ttl_days: int = DEFAULT_CACHE_TTL_DAYS,
    max_candidates_per_run: int = DEFAULT_MAX_CANDIDATES_PER_RUN,
) -> EasyScholarConfig:
    return EasyScholarConfig(
        vault_path=vault_path,
        enabled=enabled,
        secret_key=os.environ.get("EASYSCHOLAR_SECRET_KEY"),
        timeout_seconds=timeout_seconds,
        cache_ttl_days=cache_ttl_days,
        max_candidates_per_run=max_candidates_per_run,
    )
