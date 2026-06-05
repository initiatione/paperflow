# EPI Resumable Review Evidence Index Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement default-resumable EPI literature discovery plus MinerU full-text evidence indexes, following the approved spec in `docs/superpowers/specs/2026-06-06-epi-resumable-review-evidence-index-design.md`.

**Architecture:** Keep `_epi/runs` as per-invocation evidence and add `_epi/reviews` as persistent review-session state. Add focused modules for review sessions, fetch plans, and evidence indexes; wire them into existing discovery, parse, staging, report, and CLI boundaries with narrow changes. Use deterministic JSON artifacts and atomic writes throughout.

**Tech Stack:** Python 3.11, pytest, EPI local CLI under `plugins/epi/scripts`, JSON artifacts in the target vault.

---

## File Structure

- Create `plugins/epi/scripts/build/epi/review_sessions.py`
  - Owns `_epi/reviews` paths, review signatures, session lookup, session state writes, provider-cache persistence, rehydration, partial-resume decisions, and copying session artifacts into a run.
- Create `plugins/epi/scripts/build/epi/fetch_plan.py`
  - Builds `fetch_plan.json` from ranked candidates without downloading PDFs.
- Create `plugins/epi/scripts/build/epi/evidence_index.py`
  - Builds `_epi/raw/<slug>/evidence-index.json` from MinerU Markdown and updates `_epi/meta/evidence-index.json`.
- Modify `plugins/epi/scripts/build/epi/artifacts.py`
  - Add `reviews_root(vault_path)` and `review_root(vault_path, review_id)`.
- Modify `plugins/epi/scripts/build/epi/orchestrator.py`
  - Wire review sessions into `run_dry_run`.
  - Add `refresh` and `resume` parameters.
  - Call evidence-index generation after successful parse/materialized ingest paths.
- Modify `plugins/epi/scripts/build/epi/cli_parser.py`
  - Add mutually exclusive `dry-run --refresh` and `dry-run --no-resume`.
- Modify `plugins/epi/scripts/build/epi/cli.py`
  - Pass resume/refresh flags into `run_dry_run`.
  - Include review artifact paths in `dry-run --json`.
- Modify `plugins/epi/scripts/build/epi/report_run.py`
  - Render a `Review Session` Markdown section and preserve `discovery_context.review_session` in JSON.
- Modify `plugins/epi/scripts/build/epi/run_mineru_parse.py`
  - Generate evidence index after successful `run_mineru_command` and `materialize_mineru_fixture`.
- Modify `plugins/epi/scripts/build/epi/stage_wiki.py`
  - Add evidence-index path, chunk count, input hashes, and warnings to `source_bundle.evidence`.
- Modify `plugins/epi/scripts/build/epi/wiki_ingest_handoff.py`
  - Add evidence-index locator cues to the handoff checklist and handoff payload.
- Modify `plugins/epi/scripts/build/epi/epi_repository.py`
  - Ensure repository cleanup does not target `_epi/reviews`.
- Add `tests/epi/test_review_sessions.py`
  - Unit tests for signature, session lookup, provider-cache persistence, partial resume, and corrupt-state handling.
- Add `tests/epi/test_evidence_index.py`
  - Unit tests for deterministic chunking, page locator handling, aggregate updates, and source hashes.
- Modify `tests/epi/test_orchestrator_dry_run.py`
  - Integration tests for default resume, refresh, and run/report metadata.
- Modify `tests/epi/test_cli_parser.py`
  - Parser and CLI JSON tests for resume/refresh flags and review output.
- Modify `tests/epi/test_mineru_parse_adapter.py`
  - Tests that parse success writes per-paper and aggregate evidence indexes.
- Modify `tests/epi/test_one_paper_ingest.py`
  - Tests that staging brief exposes evidence-index paths.
- Modify `tests/epi/test_wiki_ingest_handoff.py`
  - Tests that handoff payload/checklist exposes evidence-index locators.
- Modify docs:
  - `plugins/epi/docs/epi-linkage.md`
  - `plugins/epi/docs/structure.md`
  - `plugins/epi/docs/workflow.md`
  - `plugins/epi/skills/paper-discovery/workflows/run-discovery.md`
  - `plugins/epi/skills/paper-ingest/workflows/prepare-ranked.md`
  - `plugins/epi/skills/wiki-provenance/SKILL.md`

---

### Task 0: Create Isolated Workspace

**Files:**
- No repository file changes expected unless `.worktrees/` must be added to `.gitignore`.

- [ ] **Step 1: Detect existing worktree state**

Run:

```powershell
git rev-parse --git-dir
git rev-parse --git-common-dir
git rev-parse --show-superproject-working-tree
git branch --show-current
git status --short --branch
```

Expected: current checkout is normal `main`, not a linked worktree. It may be dirty because prior user changes exist.

- [ ] **Step 2: Verify project-local worktree directory ignore**

Run:

```powershell
git check-ignore -q .worktrees; if ($LASTEXITCODE -eq 0) { "ignored" } else { "not-ignored" }
```

Expected: `ignored`. If it prints `not-ignored`, add `.worktrees/` to `.gitignore`, commit only that `.gitignore` change, then continue.

- [ ] **Step 3: Create feature worktree**

Run:

```powershell
git worktree add .worktrees\epi-resumable-review -b feat/epi-resumable-review
```

Expected: new worktree created at `D:\paper-search\.worktrees\epi-resumable-review`.

- [ ] **Step 4: Enter worktree and verify clean baseline status**

Run:

```powershell
Set-Location D:\paper-search\.worktrees\epi-resumable-review
git status --short --branch
```

Expected: branch `feat/epi-resumable-review` and clean status.

- [ ] **Step 5: Run focused baseline tests**

Run:

```powershell
python -m pytest tests\epi\test_orchestrator_dry_run.py tests\epi\test_cli_parser.py tests\epi\test_mineru_parse_adapter.py tests\epi\test_wiki_ingest_handoff.py -q --basetemp=.pytest_tmp_epi_resume_baseline
```

Expected: all selected tests pass before implementation. If they fail, record failures and decide whether they are caused by branch baseline or environment.

---

### Task 1: Review Session Unit Model

**Files:**
- Create: `plugins/epi/scripts/build/epi/review_sessions.py`
- Create: `plugins/epi/scripts/build/epi/fetch_plan.py`
- Modify: `plugins/epi/scripts/build/epi/artifacts.py`
- Test: `tests/epi/test_review_sessions.py`

- [ ] **Step 1: Write failing review-session unit tests**

Create `tests/epi/test_review_sessions.py`:

```python
import json

import pytest

from epi.artifacts import review_root, reviews_root
from epi.fetch_plan import build_fetch_plan
from epi.review_sessions import (
    build_review_signature,
    create_or_update_review_session,
    find_matching_review_session,
    load_review_session_for_resume,
    persist_provider_cache_records,
    rehydrate_search_record_from_review,
)


def _signature_inputs():
    return {
        "query": "robotics navigation control",
        "query_plan": {
            "domain": "profile-derived",
            "query_variants": [
                "robotics navigation control -review -survey",
                "mobile robot control navigation -review -survey",
            ],
        },
        "requested_sources": ["arxiv", "semantic"],
        "effective_sources": ["arxiv", "semantic"],
        "source_routing": {"selected_sources": ["arxiv", "semantic"]},
        "max_results": 5,
        "profile": "robotics_ai_control",
        "domains": ["robotics", "control"],
        "positive_keywords": ["navigation"],
        "negative_keywords": ["survey"],
        "venue_prior": {"IROS": 2.0},
        "use_query_plan": True,
        "query_plan_domain": "auto",
        "query_plan_max_queries": 6,
        "enable_easyscholar": True,
    }


def _search_record():
    return {
        "source_mode": "fixture",
        "query_strategy": "query_plan_multi_query",
        "records": [
            {
                "source": "fixture",
                "title": "Robot Navigation Control",
                "authors": ["A. Researcher"],
                "year": 2025,
                "venue": "IROS",
                "abstract": "robotics navigation control",
                "pdf_url": "https://example.org/paper.pdf",
                "citation_count": 7,
            }
        ],
        "query_records": [
            {
                "index": 1,
                "query": "robotics navigation control -review -survey",
                "source_mode": "fixture",
                "record_count": 1,
                "upstream": {"source_results": {"fixture": 1}, "raw_total": 1},
            }
        ],
        "warnings": [],
        "upstream": {"source_results": {"fixture": 1}, "raw_total": 1},
    }


def test_review_signature_is_stable_and_ignores_timestamps():
    first = build_review_signature({**_signature_inputs(), "created_at": "one"})
    second = build_review_signature({**_signature_inputs(), "created_at": "two"})
    changed = build_review_signature({**_signature_inputs(), "max_results": 10})

    assert first["signature"] == second["signature"]
    assert first["signature"] != changed["signature"]
    assert first["signature_inputs"]["query"] == "robotics navigation control"
    assert "created_at" not in first["signature_inputs"]


def test_review_session_writes_state_and_artifacts(tmp_path):
    vault = tmp_path / "vault"
    signature = build_review_signature(_signature_inputs())
    ranked = [{"slug": "robot-navigation-control", "title": "Robot Navigation Control", "doi": "10.1000/robot"}]
    session = create_or_update_review_session(
        vault,
        topic="robotics navigation control",
        signature=signature,
        query_plan=_signature_inputs()["query_plan"],
        search_record=_search_record(),
        normalized=_search_record()["records"],
        filter_report={"kept": ranked, "rejected": []},
        easyscholar_record={"enabled": False, "summary": {"disabled": 1}},
        ranked_pool=ranked,
        accepted=ranked,
        coverage={"sources_used": ["fixture"], "raw_total": 1, "deduped_total": 1},
        run_id="run-001",
        refreshed=False,
    )

    root = review_root(vault, session["review_id"])
    assert reviews_root(vault).is_dir()
    assert (root / "state.json").is_file()
    assert (root / "query-plan.json").is_file()
    assert (root / "candidates.json").is_file()
    assert (root / "shortlist.json").is_file()
    assert (root / "fetch_plan.json").is_file()
    assert (root / "coverage.json").is_file()
    assert (root / "provider-cache" / "query-01.json").is_file()
    assert (root / "runs" / "run-001.json").is_file()
    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    assert state["schema_version"] == "epi-review-session-v1"
    assert state["phase"] == "ranked"
    assert state["resume_count"] == 0
    assert state["refresh_count"] == 0
    assert state["candidate_counts"]["accepted"] == 1
    fetch_plan = json.loads((root / "fetch_plan.json").read_text(encoding="utf-8"))
    assert fetch_plan["items"][0]["slug"] == "robot-navigation-control"
    assert fetch_plan["items"][0]["doi"] == "10.1000/robot"


def test_find_matching_review_session_and_rehydrate_search_record(tmp_path):
    vault = tmp_path / "vault"
    signature = build_review_signature(_signature_inputs())
    session = create_or_update_review_session(
        vault,
        topic="robotics navigation control",
        signature=signature,
        query_plan=_signature_inputs()["query_plan"],
        search_record=_search_record(),
        normalized=_search_record()["records"],
        filter_report={"kept": _search_record()["records"], "rejected": []},
        easyscholar_record={"enabled": False, "summary": {"disabled": 1}},
        ranked_pool=_search_record()["records"],
        accepted=_search_record()["records"],
        coverage={"sources_used": ["fixture"], "raw_total": 1, "deduped_total": 1},
        run_id="run-001",
        refreshed=False,
    )

    found = find_matching_review_session(vault, signature["signature"])
    assert found["review_id"] == session["review_id"]
    loaded = load_review_session_for_resume(vault, signature["signature"])
    assert loaded["state"]["review_id"] == session["review_id"]
    search_record = rehydrate_search_record_from_review(loaded)
    assert search_record["resumed"] is True
    assert search_record["provider_call_skipped"] is True
    assert search_record["records"][0]["title"] == "Robot Navigation Control"


def test_provider_cache_can_rebuild_candidates_when_candidates_json_missing(tmp_path):
    vault = tmp_path / "vault"
    signature = build_review_signature(_signature_inputs())
    session = create_or_update_review_session(
        vault,
        topic="robotics navigation control",
        signature=signature,
        query_plan=_signature_inputs()["query_plan"],
        search_record=_search_record(),
        normalized=_search_record()["records"],
        filter_report={"kept": _search_record()["records"], "rejected": []},
        easyscholar_record={"enabled": False, "summary": {"disabled": 1}},
        ranked_pool=_search_record()["records"],
        accepted=_search_record()["records"],
        coverage={"sources_used": ["fixture"], "raw_total": 1, "deduped_total": 1},
        run_id="run-001",
        refreshed=False,
    )
    root = review_root(vault, session["review_id"])
    (root / "candidates.json").unlink()

    loaded = load_review_session_for_resume(vault, signature["signature"])
    assert loaded["resume_phase"] == "provider-cache"
    rebuilt = rehydrate_search_record_from_review(loaded)
    assert rebuilt["records"][0]["title"] == "Robot Navigation Control"
    assert rebuilt["provider_call_skipped"] is True


def test_corrupt_review_state_requires_refresh(tmp_path):
    vault = tmp_path / "vault"
    signature = build_review_signature(_signature_inputs())
    session = create_or_update_review_session(
        vault,
        topic="robotics navigation control",
        signature=signature,
        query_plan=_signature_inputs()["query_plan"],
        search_record=_search_record(),
        normalized=_search_record()["records"],
        filter_report={"kept": _search_record()["records"], "rejected": []},
        easyscholar_record={"enabled": False, "summary": {"disabled": 1}},
        ranked_pool=_search_record()["records"],
        accepted=_search_record()["records"],
        coverage={"sources_used": ["fixture"], "raw_total": 1, "deduped_total": 1},
        run_id="run-001",
        refreshed=False,
    )
    (review_root(vault, session["review_id"]) / "shortlist.json").write_text("{bad json", encoding="utf-8")

    with pytest.raises(ValueError, match="corrupt review session"):
        load_review_session_for_resume(vault, signature["signature"])


def test_build_fetch_plan_preserves_pdf_and_manual_links():
    ranked = [
        {
            "slug": "manual-paper",
            "title": "Manual Paper",
            "doi": "10.1000/manual",
            "arxiv_id": "2501.12345",
            "pdf_url": "https://example.org/main.pdf",
            "pdf_urls": ["https://example.org/main.pdf"],
            "alternate_pdf_urls": [{"source": "semantic", "url": "https://example.org/alt.pdf"}],
            "raw_records": [{"source": "arxiv", "paper_id": "2501.12345"}],
        }
    ]

    plan = build_fetch_plan(ranked)

    assert plan["schema_version"] == "epi-fetch-plan-v1"
    assert plan["items"][0]["slug"] == "manual-paper"
    assert plan["items"][0]["candidate_pdf_urls"] == [
        "https://example.org/main.pdf",
        "https://example.org/alt.pdf",
    ]
    assert plan["items"][0]["source_identities"] == [{"source": "arxiv", "paper_id": "2501.12345"}]
    assert plan["items"][0]["manual_download"]["doi_url"] == "https://doi.org/10.1000/manual"
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest tests\epi\test_review_sessions.py -q --basetemp=.pytest_tmp_epi_review_red
```

Expected: fail with import errors for `epi.review_sessions`, `epi.fetch_plan`, or missing `review_root`.

- [ ] **Step 3: Implement artifact roots**

Modify `plugins/epi/scripts/build/epi/artifacts.py`:

```python
def reviews_root(vault_path: Path) -> Path:
    return epi_root(vault_path) / "reviews"


def review_root(vault_path: Path, review_id: str) -> Path:
    return reviews_root(vault_path) / review_id
```

- [ ] **Step 4: Implement fetch plan module**

Create `plugins/epi/scripts/build/epi/fetch_plan.py`:

```python
from __future__ import annotations

from epi.artifacts import utc_now


def _unique_text(values: list[object]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _pdf_urls(candidate: dict) -> list[str]:
    values: list[object] = [candidate.get("pdf_url")]
    raw_pdf_urls = candidate.get("pdf_urls")
    if isinstance(raw_pdf_urls, list):
        values.extend(raw_pdf_urls)
    alternate_pdf_urls = candidate.get("alternate_pdf_urls")
    if isinstance(alternate_pdf_urls, list):
        for item in alternate_pdf_urls:
            values.append(item.get("url") if isinstance(item, dict) else item)
    return _unique_text(values)


def _source_identities(candidate: dict) -> list[dict]:
    identities: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for record in candidate.get("raw_records") or []:
        if not isinstance(record, dict):
            continue
        raw_record = record.get("raw_record") if isinstance(record.get("raw_record"), dict) else {}
        source = str(raw_record.get("source") or record.get("source") or "").strip().lower()
        paper_id = raw_record.get("paper_id") or record.get("paper_id")
        if not paper_id and source == "arxiv":
            paper_id = record.get("arxiv_id") or candidate.get("arxiv_id")
        paper_id_text = str(paper_id or "").strip()
        if not source or not paper_id_text:
            continue
        key = (source, paper_id_text)
        if key in seen:
            continue
        seen.add(key)
        identities.append({"source": source, "paper_id": paper_id_text})
    if candidate.get("arxiv_id") and ("arxiv", str(candidate["arxiv_id"])) not in seen:
        identities.append({"source": "arxiv", "paper_id": str(candidate["arxiv_id"])})
    return identities


def _doi_url(doi: object) -> str | None:
    text = str(doi or "").strip()
    if not text:
        return None
    if text.lower().startswith(("http://", "https://")):
        return text
    return f"https://doi.org/{text}"


def _manual_download(candidate: dict, pdf_urls: list[str]) -> dict:
    urls: list[dict] = []
    doi_url = _doi_url(candidate.get("doi"))
    if doi_url:
        urls.append({"kind": "doi", "url": doi_url})
    for url in pdf_urls:
        urls.append({"kind": "publisher_pdf", "url": url})
    return {
        "required": not bool(pdf_urls),
        "doi_url": doi_url,
        "candidate_manual_urls": urls,
        "preferred_next_step": (
            "Use DOI/publisher/open-access links to provide a local PDF or direct open-access PDF URL."
        ),
    }


def build_fetch_plan(ranked_candidates: list[dict]) -> dict:
    items = []
    for candidate in ranked_candidates:
        urls = _pdf_urls(candidate)
        items.append(
            {
                "slug": candidate.get("slug"),
                "title": candidate.get("title"),
                "doi": candidate.get("doi"),
                "arxiv_id": candidate.get("arxiv_id"),
                "candidate_pdf_urls": urls,
                "source_identities": _source_identities(candidate),
                "manual_download": _manual_download(candidate, urls),
                "recommended_order": [
                    "paper-search-mcp-download-with-fallback",
                    "source-native-download",
                    "direct-pdf-url",
                    "manual-download",
                ],
                "known_blockers": [],
            }
        )
    return {
        "schema_version": "epi-fetch-plan-v1",
        "created_at": utc_now(),
        "item_count": len(items),
        "items": items,
    }
```

- [ ] **Step 5: Implement review session module**

Create `plugins/epi/scripts/build/epi/review_sessions.py` with:

```python
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from epi.artifacts import json_sha256, review_root, reviews_root, utc_now, write_json_atomic
from epi.fetch_plan import build_fetch_plan
from epi.schemas import slugify_title


SCHEMA_VERSION = "epi-review-session-v1"


def _clean_signature_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _clean_signature_value(value[key])
            for key in sorted(value)
            if key not in {"created_at", "updated_at", "started_at", "finished_at", "run_id"}
        }
    if isinstance(value, list):
        return [_clean_signature_value(item) for item in value]
    if isinstance(value, str):
        return " ".join(value.split())
    return value


def build_review_signature(inputs: dict[str, Any]) -> dict[str, Any]:
    cleaned = _clean_signature_value(inputs)
    return {
        "schema_version": "epi-review-signature-v1",
        "signature": json_sha256(cleaned),
        "signature_inputs": cleaned,
    }


def _review_id(topic: str, signature: str) -> str:
    slug = slugify_title(topic or "review")
    slug = re.sub(r"-+", "-", slug).strip("-") or "review"
    return f"{slug[:64]}-{signature[:12]}"


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"corrupt review session artifact: {path}") from exc


def _read_json_if_exists(path: Path) -> Any | None:
    if not path.exists():
        return None
    return _read_json(path)


def _provider_cache_records(search_record: dict[str, Any]) -> list[dict[str, Any]]:
    query_records = search_record.get("query_records")
    if isinstance(query_records, list) and query_records:
        records = []
        all_records = search_record.get("records") or []
        for item in query_records:
            if not isinstance(item, dict):
                continue
            records.append(
                {
                    "schema_version": "epi-provider-cache-record-v1",
                    "query_index": item.get("index"),
                    "query": item.get("query"),
                    "source_mode": item.get("source_mode"),
                    "record_count": item.get("record_count", 0),
                    "records": [
                        record
                        for record in all_records
                        if record.get("query_variant") == item.get("query")
                    ],
                    "upstream": item.get("upstream", {}),
                    "error": item.get("error"),
                    "warnings": [],
                    "created_at": utc_now(),
                    "provider_call": {"called": True, "reason": "refresh_or_cache_miss"},
                }
            )
        return records
    return [
        {
            "schema_version": "epi-provider-cache-record-v1",
            "query_index": 1,
            "query": search_record.get("query"),
            "source_mode": search_record.get("source_mode"),
            "record_count": len(search_record.get("records") or []),
            "records": search_record.get("records") or [],
            "upstream": search_record.get("upstream", {}),
            "error": search_record.get("error"),
            "warnings": search_record.get("warnings", []),
            "created_at": utc_now(),
            "provider_call": {"called": True, "reason": "refresh_or_cache_miss"},
        }
    ]


def persist_provider_cache_records(root: Path, search_record: dict[str, Any], review_id: str) -> list[str]:
    cache_root = root / "provider-cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for index, record in enumerate(_provider_cache_records(search_record), start=1):
        payload = dict(record)
        payload["review_id"] = review_id
        path = cache_root / f"query-{index:02d}.json"
        write_json_atomic(path, payload)
        paths.append(path.relative_to(root).as_posix())
    return paths


def _candidate_counts(records: list[dict], normalized: list[dict], filter_report: dict, ranked_pool: list[dict], accepted: list[dict]) -> dict:
    return {
        "raw": len(records),
        "normalized": len(normalized),
        "filtered": len(filter_report.get("kept") or []),
        "ranked": len(ranked_pool),
        "accepted": len(accepted),
        "rejected": len(filter_report.get("rejected") or []),
    }


def create_or_update_review_session(
    vault_path: Path,
    *,
    topic: str,
    signature: dict[str, Any],
    query_plan: dict[str, Any] | None,
    search_record: dict[str, Any],
    normalized: list[dict],
    filter_report: dict,
    easyscholar_record: dict,
    ranked_pool: list[dict],
    accepted: list[dict],
    coverage: dict,
    run_id: str,
    refreshed: bool,
) -> dict[str, Any]:
    review_id = _review_id(topic, signature["signature"])
    root = review_root(vault_path, review_id)
    root.mkdir(parents=True, exist_ok=True)
    now = utc_now()
    existing_state = _read_json_if_exists(root / "state.json") or {}
    run_ids = list(existing_state.get("run_ids") or [])
    if run_id not in run_ids:
        run_ids.append(run_id)
    provider_paths = persist_provider_cache_records(root, search_record, review_id)
    write_json_atomic(root / "signature-inputs.json", signature["signature_inputs"])
    if query_plan:
        write_json_atomic(root / "query-plan.json", query_plan)
    candidates = {
        "schema_version": "epi-review-candidates-v1",
        "review_id": review_id,
        "records": search_record.get("records") or [],
        "normalized": normalized,
        "source_record_paths": provider_paths,
        "record_count": len(search_record.get("records") or []),
        "normalized_count": len(normalized),
    }
    shortlist = {
        "schema_version": "epi-review-shortlist-v1",
        "review_id": review_id,
        "kept": filter_report.get("kept") or [],
        "rejected": filter_report.get("rejected") or [],
        "ranked_pool": ranked_pool,
        "accepted": accepted,
        "filter_report_path": "filter-report.json",
        "easyscholar_record": easyscholar_record,
    }
    write_json_atomic(root / "candidates.json", candidates)
    write_json_atomic(root / "filter-report.json", filter_report)
    write_json_atomic(root / "shortlist.json", shortlist)
    write_json_atomic(root / "fetch_plan.json", build_fetch_plan(accepted))
    write_json_atomic(root / "coverage.json", {"schema_version": "epi-review-coverage-v1", "review_id": review_id, **coverage})
    write_json_atomic(root / "runs" / f"{run_id}.json", {"run_id": run_id, "recorded_at": now, "refreshed": refreshed})
    state = {
        "schema_version": SCHEMA_VERSION,
        "review_id": review_id,
        "topic": topic,
        "normalized_topic": " ".join(topic.lower().split()),
        "signature": signature["signature"],
        "signature_inputs_path": "signature-inputs.json",
        "status": "active",
        "phase": "ranked",
        "created_at": existing_state.get("created_at") or now,
        "updated_at": now,
        "last_run_id": run_id,
        "run_ids": run_ids,
        "resume_count": int(existing_state.get("resume_count") or 0),
        "refresh_count": int(existing_state.get("refresh_count") or 0) + (1 if refreshed else 0),
        "candidate_counts": _candidate_counts(search_record.get("records") or [], normalized, filter_report, ranked_pool, accepted),
        "artifacts": {
            "query_plan": "query-plan.json" if query_plan else None,
            "candidates": "candidates.json",
            "shortlist": "shortlist.json",
            "fetch_plan": "fetch_plan.json",
            "coverage": "coverage.json",
        },
    }
    write_json_atomic(root / "state.json", state)
    return {"review_id": review_id, "review_dir": str(root), "state": state}


def find_matching_review_session(vault_path: Path, signature: str) -> dict[str, Any] | None:
    root = reviews_root(vault_path)
    if not root.exists():
        return None
    for candidate in sorted(path for path in root.iterdir() if path.is_dir()):
        state = _read_json_if_exists(candidate / "state.json")
        if isinstance(state, dict) and state.get("status") == "active" and state.get("signature") == signature:
            return {"review_id": state["review_id"], "review_dir": str(candidate), "state": state}
    return None


def load_review_session_for_resume(vault_path: Path, signature: str) -> dict[str, Any]:
    match = find_matching_review_session(vault_path, signature)
    if not match:
        raise FileNotFoundError("no matching review session")
    root = Path(match["review_dir"])
    candidates = _read_json_if_exists(root / "candidates.json")
    shortlist = _read_json_if_exists(root / "shortlist.json")
    coverage = _read_json_if_exists(root / "coverage.json")
    provider_cache_paths = sorted((root / "provider-cache").glob("query-*.json"))
    provider_cache = [_read_json(path) for path in provider_cache_paths]
    if shortlist is not None:
        phase = "shortlist"
    elif candidates is not None:
        phase = "candidates"
    elif provider_cache:
        phase = "provider-cache"
    else:
        raise ValueError(f"corrupt review session: {root}")
    return {
        **match,
        "root": root,
        "candidates": candidates,
        "shortlist": shortlist,
        "coverage": coverage,
        "provider_cache": provider_cache,
        "resume_phase": phase,
    }


def mark_review_resumed(session: dict[str, Any], run_id: str) -> dict[str, Any]:
    root = Path(session["review_dir"])
    state = dict(session["state"])
    run_ids = list(state.get("run_ids") or [])
    if run_id not in run_ids:
        run_ids.append(run_id)
    state["run_ids"] = run_ids
    state["last_run_id"] = run_id
    state["resume_count"] = int(state.get("resume_count") or 0) + 1
    state["updated_at"] = utc_now()
    write_json_atomic(root / "state.json", state)
    write_json_atomic(root / "runs" / f"{run_id}.json", {"run_id": run_id, "recorded_at": state["updated_at"], "resumed": True})
    session["state"] = state
    return state


def rehydrate_search_record_from_review(session: dict[str, Any]) -> dict[str, Any]:
    if session.get("candidates") and isinstance(session["candidates"], dict):
        records = session["candidates"].get("records") or []
    else:
        records = []
        for cache_record in session.get("provider_cache") or []:
            records.extend(cache_record.get("records") or [])
    query_records = []
    for cache_record in session.get("provider_cache") or []:
        query_records.append(
            {
                "index": cache_record.get("query_index"),
                "query": cache_record.get("query"),
                "source_mode": cache_record.get("source_mode"),
                "record_count": cache_record.get("record_count", len(cache_record.get("records") or [])),
                "error": cache_record.get("error"),
                "upstream": cache_record.get("upstream", {}),
            }
        )
    return {
        "source_mode": "review-session",
        "query_strategy": "review_session_resume",
        "records": records,
        "query_records": query_records,
        "warnings": [],
        "resumed": True,
        "resumed_from_review_id": session["review_id"],
        "provider_call_skipped": True,
        "upstream": {},
    }


def review_artifact_paths(session: dict[str, Any]) -> dict[str, str]:
    root = Path(session["review_dir"])
    return {
        "state": str(root / "state.json"),
        "candidates": str(root / "candidates.json"),
        "shortlist": str(root / "shortlist.json"),
        "fetch_plan": str(root / "fetch_plan.json"),
        "coverage": str(root / "coverage.json"),
    }
```

- [ ] **Step 6: Run unit tests and verify GREEN**

Run:

```powershell
python -m pytest tests\epi\test_review_sessions.py -q --basetemp=.pytest_tmp_epi_review_green
```

Expected: all tests in `test_review_sessions.py` pass.

- [ ] **Step 7: Commit Task 1**

Run:

```powershell
git add plugins\epi\scripts\build\epi\artifacts.py plugins\epi\scripts\build\epi\fetch_plan.py plugins\epi\scripts\build\epi\review_sessions.py tests\epi\test_review_sessions.py
git commit -m "feat: add EPI review session artifacts"
```

Expected: commit succeeds.

---

### Task 2: CLI Resume Flags and Dry-Run Review JSON Surface

**Files:**
- Modify: `plugins/epi/scripts/build/epi/cli_parser.py`
- Modify: `plugins/epi/scripts/build/epi/cli.py`
- Test: `tests/epi/test_cli_parser.py`

- [ ] **Step 1: Write failing CLI tests**

Append to `tests/epi/test_cli_parser.py`:

```python

def test_dry_run_parser_accepts_refresh_and_no_resume_as_exclusive_options():
    refresh_args = build_parser().parse_args(
        [
            "dry-run",
            "--query",
            "robotics control",
            "--refresh",
        ]
    )
    no_resume_args = build_parser().parse_args(
        [
            "dry-run",
            "--query",
            "robotics control",
            "--no-resume",
        ]
    )

    assert refresh_args.refresh is True
    assert refresh_args.no_resume is False
    assert no_resume_args.refresh is False
    assert no_resume_args.no_resume is True


def test_dry_run_parser_rejects_refresh_with_no_resume():
    import pytest

    with pytest.raises(SystemExit):
        build_parser().parse_args(
            [
                "dry-run",
                "--query",
                "robotics control",
                "--refresh",
                "--no-resume",
            ]
        )


def test_dry_run_cli_passes_resume_and_refresh_flags(tmp_path, monkeypatch):
    run_dir = tmp_path / "_epi" / "runs" / "run-json-001"
    run_dir.mkdir(parents=True)
    captured = {}

    def fake_run_dry_run(**kwargs):
        captured.update(kwargs)
        return run_dir

    monkeypatch.setattr(cli.workflows, "run_dry_run", fake_run_dry_run)

    exit_code = cli.main(
        [
            "dry-run",
            "--query",
            "AUV reinforcement learning control",
            "--vault",
            str(tmp_path),
            "--refresh",
        ]
    )

    assert exit_code == 0
    assert captured["resume"] is True
    assert captured["refresh"] is True


def test_dry_run_cli_json_includes_review_artifacts_when_present(tmp_path, monkeypatch, capsys):
    run_dir = tmp_path / "_epi" / "runs" / "run-json-001"
    run_dir.mkdir(parents=True)
    for name in ["search-record.json", "rank.json", "report.md", "report.json", "run-state.json"]:
        (run_dir / name).write_text("{}", encoding="utf-8")
    review_dir = tmp_path / "_epi" / "reviews" / "robotics-abc"
    review_dir.mkdir(parents=True)
    for name in ["state.json", "candidates.json", "shortlist.json", "fetch_plan.json", "coverage.json"]:
        (review_dir / name).write_text("{}", encoding="utf-8")
    (run_dir / "run-state.json").write_text(
        __import__("json").dumps(
            {
                "review_session": {
                    "review_id": "robotics-abc",
                    "review_dir": str(review_dir),
                    "resumed": True,
                    "refreshed": False,
                    "provider_call_skipped": True,
                    "artifacts": {
                        "state": str(review_dir / "state.json"),
                        "candidates": str(review_dir / "candidates.json"),
                        "shortlist": str(review_dir / "shortlist.json"),
                        "fetch_plan": str(review_dir / "fetch_plan.json"),
                        "coverage": str(review_dir / "coverage.json"),
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    def fake_run_dry_run(**kwargs):
        return run_dir

    monkeypatch.setattr(cli.workflows, "run_dry_run", fake_run_dry_run)

    exit_code = cli.main(
        [
            "dry-run",
            "--query",
            "robotics control",
            "--vault",
            str(tmp_path),
            "--json",
        ]
    )

    payload = __import__("json").loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["review"]["review_id"] == "robotics-abc"
    assert payload["review"]["provider_call_skipped"] is True
    assert payload["review"]["artifacts"]["fetch_plan"] == str(review_dir / "fetch_plan.json")
```

- [ ] **Step 2: Run CLI tests and verify RED**

Run:

```powershell
python -m pytest tests\epi\test_cli_parser.py::test_dry_run_parser_accepts_refresh_and_no_resume_as_exclusive_options tests\epi\test_cli_parser.py::test_dry_run_parser_rejects_refresh_with_no_resume tests\epi\test_cli_parser.py::test_dry_run_cli_passes_resume_and_refresh_flags tests\epi\test_cli_parser.py::test_dry_run_cli_json_includes_review_artifacts_when_present -q --basetemp=.pytest_tmp_epi_cli_red
```

Expected: fail because parser flags and CLI JSON review output are missing.

- [ ] **Step 3: Add dry-run mutually exclusive parser flags**

Modify `plugins/epi/scripts/build/epi/cli_parser.py` after `dry_run.add_argument("--no-easyscholar", action="store_true")`:

```python
    dry_run_resume_group = dry_run.add_mutually_exclusive_group()
    dry_run_resume_group.add_argument("--refresh", action="store_true")
    dry_run_resume_group.add_argument("--no-resume", action="store_true")
```

- [ ] **Step 4: Pass flags and emit review JSON**

Modify `_handle_dry_run` in `plugins/epi/scripts/build/epi/cli.py`:

```python
        enable_easyscholar=not args.no_easyscholar,
        resume=not args.no_resume,
        refresh=args.refresh,
```

Add helper near `_load_json`:

```python
def _run_review_payload(run_dir: Path) -> dict | None:
    state_path = run_dir / "run-state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    review = state.get("review_session")
    return review if isinstance(review, dict) else None
```

In JSON payload construction, add:

```python
        review_payload = _run_review_payload(run_dir)
        if review_payload:
            payload["review"] = review_payload
```

- [ ] **Step 5: Run CLI tests and verify GREEN**

Run:

```powershell
python -m pytest tests\epi\test_cli_parser.py -q --basetemp=.pytest_tmp_epi_cli_green
```

Expected: CLI parser tests pass.

- [ ] **Step 6: Commit Task 2**

Run:

```powershell
git add plugins\epi\scripts\build\epi\cli_parser.py plugins\epi\scripts\build\epi\cli.py tests\epi\test_cli_parser.py
git commit -m "feat: expose dry-run review resume flags"
```

Expected: commit succeeds.

---

### Task 3: Integrate Default Resume into `run_dry_run`

**Files:**
- Modify: `plugins/epi/scripts/build/epi/orchestrator.py`
- Modify: `plugins/epi/scripts/build/epi/report_run.py`
- Test: `tests/epi/test_orchestrator_dry_run.py`

- [ ] **Step 1: Write failing dry-run resume integration tests**

Append to `tests/epi/test_orchestrator_dry_run.py`:

```python

def test_dry_run_resumes_matching_review_session_by_default_without_provider_call(tmp_path):
    plugin_root = tmp_path / "plugin"
    _write_minimal_plugin_template(plugin_root)
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "source": "fixture",
                    "title": "Embodied Navigation Control for Mobile Robots",
                    "authors": ["B. Engineer"],
                    "year": 2024,
                    "venue": "IROS",
                    "abstract": "Robotics navigation and control with code.",
                    "pdf_url": "https://example.org/nav.pdf",
                    "citation_count": 9,
                }
            ]
        ),
        encoding="utf-8",
    )
    vault = tmp_path / "vault"
    first_run = run_dry_run(
        plugin_root=plugin_root,
        vault_path=vault,
        query="robotics navigation control",
        max_results=5,
        fixture_path=fixture,
        enable_easyscholar=False,
    )
    fixture.write_text("[]", encoding="utf-8")

    second_run = run_dry_run(
        plugin_root=plugin_root,
        vault_path=vault,
        query="robotics navigation control",
        max_results=5,
        fixture_path=fixture,
        enable_easyscholar=False,
    )

    assert first_run != second_run
    second_state = json.loads((second_run / "run-state.json").read_text(encoding="utf-8"))
    second_search = json.loads((second_run / "search-record.json").read_text(encoding="utf-8"))
    second_report = json.loads((second_run / "report.json").read_text(encoding="utf-8"))
    second_ranked = json.loads((second_run / "rank.json").read_text(encoding="utf-8"))
    assert second_state["review_session"]["resumed"] is True
    assert second_state["review_session"]["provider_call_skipped"] is True
    assert second_search["provider_call_skipped"] is True
    assert second_ranked[0]["title"] == "Embodied Navigation Control for Mobile Robots"
    assert second_report["discovery_context"]["review_session"]["provider_call_skipped"] is True
    assert "## Review Session" in (second_run / "report.md").read_text(encoding="utf-8")


def test_dry_run_refresh_bypasses_review_cache(tmp_path):
    plugin_root = tmp_path / "plugin"
    _write_minimal_plugin_template(plugin_root)
    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "source": "fixture",
                    "title": "Old Robot Navigation Control",
                    "authors": ["B. Engineer"],
                    "year": 2024,
                    "venue": "IROS",
                    "abstract": "robotics navigation control",
                    "pdf_url": "https://example.org/old.pdf",
                    "citation_count": 9,
                }
            ]
        ),
        encoding="utf-8",
    )
    vault = tmp_path / "vault"
    run_dry_run(
        plugin_root=plugin_root,
        vault_path=vault,
        query="robotics navigation control",
        max_results=5,
        fixture_path=fixture,
        enable_easyscholar=False,
    )
    fixture.write_text(
        json.dumps(
            [
                {
                    "source": "fixture",
                    "title": "Fresh Robot Navigation Control",
                    "authors": ["B. Engineer"],
                    "year": 2026,
                    "venue": "IROS",
                    "abstract": "robotics navigation control",
                    "pdf_url": "https://example.org/fresh.pdf",
                    "citation_count": 11,
                }
            ]
        ),
        encoding="utf-8",
    )

    refreshed_run = run_dry_run(
        plugin_root=plugin_root,
        vault_path=vault,
        query="robotics navigation control",
        max_results=5,
        fixture_path=fixture,
        enable_easyscholar=False,
        refresh=True,
    )

    state = json.loads((refreshed_run / "run-state.json").read_text(encoding="utf-8"))
    ranked = json.loads((refreshed_run / "rank.json").read_text(encoding="utf-8"))
    assert state["review_session"]["resumed"] is False
    assert state["review_session"]["refreshed"] is True
    assert state["review_session"]["provider_call_skipped"] is False
    assert ranked[0]["title"] == "Fresh Robot Navigation Control"
```

- [ ] **Step 2: Run dry-run resume tests and verify RED**

Run:

```powershell
python -m pytest tests\epi\test_orchestrator_dry_run.py::test_dry_run_resumes_matching_review_session_by_default_without_provider_call tests\epi\test_orchestrator_dry_run.py::test_dry_run_refresh_bypasses_review_cache -q --basetemp=.pytest_tmp_epi_dry_resume_red
```

Expected: fail because `run_dry_run` does not accept `refresh` and does not write review session metadata.

- [ ] **Step 3: Import review-session helpers**

Modify imports in `plugins/epi/scripts/build/epi/orchestrator.py`:

```python
from epi.review_sessions import (
    build_review_signature,
    create_or_update_review_session,
    load_review_session_for_resume,
    mark_review_resumed,
    rehydrate_search_record_from_review,
    review_artifact_paths,
)
```

- [ ] **Step 4: Extend `run_dry_run` signature and compute signature**

Change function signature:

```python
    enable_easyscholar: bool = True,
    resume: bool = True,
    refresh: bool = False,
) -> Path:
```

After query plan/source routing are built, add:

```python
    review_signature = build_review_signature(
        {
            "query": query,
            "query_plan": query_plan or {},
            "requested_sources": requested_sources,
            "effective_sources": effective_sources,
            "source_routing": source_routing,
            "max_results": config.max_results,
            "profile": config.profile,
            "domains": config.domains,
            "positive_keywords": config.positive_keywords,
            "negative_keywords": config.negative_keywords,
            "venue_prior": config.venue_prior,
            "use_query_plan": use_query_plan,
            "query_plan_domain": query_plan_domain,
            "query_plan_max_queries": query_plan_max_queries,
            "enable_easyscholar": bool(enable_easyscholar and config.easyscholar_enabled),
        }
    )
    resumed_session = None
    if resume and not refresh:
        try:
            resumed_session = load_review_session_for_resume(config.vault_path, review_signature["signature"])
        except FileNotFoundError:
            resumed_session = None
```

- [ ] **Step 5: Branch discovery through review session**

Replace direct `_run_query_plan_discovery(...)` assignment with:

```python
    if resumed_session:
        search_record = rehydrate_search_record_from_review(resumed_session)
    else:
        search_record = _run_query_plan_discovery(
            query=query,
            query_plan=query_plan,
            max_results=config.max_results,
            fixture_path=fixture_path,
            command=effective_paper_search_command,
            sources=effective_sources,
            run_dir=run_dir,
            source_routing=source_routing,
        )
```

- [ ] **Step 6: Reuse shortlist when present and write session after fresh/refresh runs**

After search record write and before filtering, keep existing normalize/filter/enrich/rank path for both fresh and resumed runs. This satisfies partial resume from provider-cache and candidates while keeping ranking deterministic. After `discovery_context` is created and before `write_report`, add:

```python
    review_session_payload = None
    if resumed_session:
        mark_review_resumed(resumed_session, run_id)
        review_session_payload = {
            "review_id": resumed_session["review_id"],
            "review_dir": str(resumed_session["review_dir"]),
            "resumed": True,
            "refreshed": False,
            "provider_call_skipped": True,
            "resume_reason": "matching_signature",
            "artifacts": review_artifact_paths(resumed_session),
        }
    else:
        session = create_or_update_review_session(
            config.vault_path,
            topic=query,
            signature=review_signature,
            query_plan=query_plan,
            search_record=search_record,
            normalized=normalized,
            filter_report=filter_report,
            easyscholar_record=easyscholar_record,
            ranked_pool=ranked_pool,
            accepted=ranked,
            coverage=_source_coverage_from_search_record(search_record, deduped_total=len(normalized)),
            run_id=run_id,
            refreshed=refresh,
        )
        review_session_payload = {
            "review_id": session["review_id"],
            "review_dir": session["review_dir"],
            "resumed": False,
            "refreshed": bool(refresh),
            "provider_call_skipped": False,
            "resume_reason": "refresh" if refresh else "created",
            "artifacts": review_artifact_paths(session),
        }
    discovery_context["review_session"] = review_session_payload
```

When final state is built, add:

```python
    state["review_session"] = review_session_payload
```

- [ ] **Step 7: Render report Review Session section**

Modify dry-run branch in `plugins/epi/scripts/build/epi/report_run.py` after Discovery Context/EasyScholar and before Next Actions:

```python
        review_session = discovery_context.get("review_session") if isinstance(discovery_context, dict) else {}
        review_session = review_session if isinstance(review_session, dict) else {}
        if review_session:
            report.append("")
            report.append("## Review Session")
            for key in ("review_id", "resumed", "provider_call_skipped", "refreshed", "resume_reason"):
                if key in review_session:
                    report.append(f"- {key}: {review_session[key]}")
            artifacts = review_session.get("artifacts") if isinstance(review_session.get("artifacts"), dict) else {}
            for key in ("candidates", "shortlist", "fetch_plan", "coverage"):
                if artifacts.get(key):
                    report.append(f"- {key}: {artifacts[key]}")
```

- [ ] **Step 8: Run dry-run tests and verify GREEN**

Run:

```powershell
python -m pytest tests\epi\test_orchestrator_dry_run.py tests\epi\test_review_sessions.py -q --basetemp=.pytest_tmp_epi_dry_resume_green
```

Expected: tests pass.

- [ ] **Step 9: Commit Task 3**

Run:

```powershell
git add plugins\epi\scripts\build\epi\orchestrator.py plugins\epi\scripts\build\epi\report_run.py tests\epi\test_orchestrator_dry_run.py
git commit -m "feat: resume EPI dry-run review sessions"
```

Expected: commit succeeds.

---

### Task 4: Evidence Index Module

**Files:**
- Create: `plugins/epi/scripts/build/epi/evidence_index.py`
- Test: `tests/epi/test_evidence_index.py`

- [ ] **Step 1: Write failing evidence-index tests**

Create `tests/epi/test_evidence_index.py`:

```python
import json

from epi.evidence_index import build_paper_evidence_index, refresh_vault_evidence_index


def _seed_paper(tmp_path, slug="fixture-paper", markdown=None):
    vault = tmp_path / "vault"
    paper_root = vault / "_epi" / "raw" / slug
    mineru = paper_root / "mineru"
    mineru.mkdir(parents=True)
    (paper_root / "paper.pdf").write_bytes(b"%PDF-1.4\nfixture\n")
    (paper_root / "metadata.json").write_text(
        json.dumps({"slug": slug, "title": "Fixture Paper", "doi": "10.1000/fixture"}),
        encoding="utf-8",
    )
    (mineru / f"{slug}.md").write_text(
        markdown
        or "# Abstract\n\n[[page:1]]\nThis is abstract evidence.\n\n## Method\n\n[[page:2]]\nThis is method evidence.\n",
        encoding="utf-8",
    )
    (mineru / "paper.tex").write_text("\\section{Method}\n", encoding="utf-8")
    (mineru / "mineru-manifest.json").write_text(json.dumps({"outputs": []}), encoding="utf-8")
    (mineru / "images").mkdir()
    return vault, paper_root


def test_build_paper_evidence_index_chunks_by_section_and_page(tmp_path):
    vault, paper_root = _seed_paper(tmp_path)

    index = build_paper_evidence_index(paper_root, vault_path=vault)

    assert index["schema_version"] == "epi-paper-evidence-index-v1"
    assert index["paper_slug"] == "fixture-paper"
    assert index["title"] == "Fixture Paper"
    assert index["source_artifacts"]["mineru_markdown"] == "mineru/fixture-paper.md"
    assert index["input_hashes"]["mineru_markdown"]
    assert len(index["chunks"]) == 2
    assert index["chunks"][0]["page"] == 1
    assert index["chunks"][0]["section_path"] == ["Abstract"]
    assert "abstract evidence" in index["chunks"][0]["text"]
    assert index["chunks"][1]["page"] == 2
    assert index["chunks"][1]["section_path"] == ["Abstract", "Method"]
    assert index["chunks"][1]["source_locator"].startswith("mineru/fixture-paper.md#")
    assert (paper_root / "evidence-index.json").is_file()


def test_build_paper_evidence_index_records_null_page_without_marker(tmp_path):
    vault, paper_root = _seed_paper(
        tmp_path,
        markdown="# Abstract\n\nNo page marker here.\n",
    )

    index = build_paper_evidence_index(paper_root, vault_path=vault)

    assert index["chunks"][0]["page"] is None
    assert "page markers not found" in index["warnings"]


def test_refresh_vault_evidence_index_records_paper_entry(tmp_path):
    vault, paper_root = _seed_paper(tmp_path)
    paper_index = build_paper_evidence_index(paper_root, vault_path=vault)

    aggregate = refresh_vault_evidence_index(vault, paper_index)

    aggregate_path = vault / "_epi" / "meta" / "evidence-index.json"
    assert aggregate_path.is_file()
    assert aggregate["schema_version"] == "epi-vault-evidence-index-v1"
    assert aggregate["papers"][0]["paper_slug"] == "fixture-paper"
    assert aggregate["papers"][0]["evidence_index"] == "_epi/raw/fixture-paper/evidence-index.json"
    assert aggregate["papers"][0]["chunk_count"] == len(paper_index["chunks"])
```

- [ ] **Step 2: Run evidence-index tests and verify RED**

Run:

```powershell
python -m pytest tests\epi\test_evidence_index.py -q --basetemp=.pytest_tmp_epi_evidence_red
```

Expected: fail because `epi.evidence_index` does not exist.

- [ ] **Step 3: Implement evidence index module**

Create `plugins/epi/scripts/build/epi/evidence_index.py`:

```python
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from epi.artifacts import epi_meta_root, file_sha256, raw_paper_root, utc_now, vault_relative, write_json_atomic
from epi.source_artifacts import resolved_mineru_markdown_relative_path, resolve_mineru_markdown_path

PAGE_MARKER = re.compile(r"^\s*(?:\[\[page:(\d+)\]\]|<!--\s*page[:=\s]+(\d+)\s*-->|-{3,}\s*page\s+(\d+)\s*-{3,})\s*$", re.I)
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def _load_metadata(paper_root: Path) -> dict[str, Any]:
    try:
        payload = json.loads((paper_root / "metadata.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _chunk_hash(payload: dict[str, Any]) -> str:
    basis = json.dumps(
        {
            "page": payload.get("page"),
            "section_path": payload.get("section_path"),
            "text": payload.get("text"),
            "source_locator": payload.get("source_locator"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def _slug_fragment(section_path: list[str], chunk_index: int) -> str:
    section = "-".join(section_path[-2:]) if section_path else "document"
    section = re.sub(r"[^a-z0-9]+", "-", section.lower()).strip("-") or "document"
    return f"{section}:c{chunk_index:04d}"


def _split_paragraph_chunks(text: str, max_chars: int, overlap_chars: int) -> list[tuple[int, int, str]]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    chunks: list[tuple[int, int, str]] = []
    offset = 0
    current: list[str] = []
    current_start = 0
    current_len = 0
    for paragraph in paragraphs:
        paragraph_start = text.find(paragraph, offset)
        if paragraph_start < 0:
            paragraph_start = offset
        candidate_len = current_len + (2 if current else 0) + len(paragraph)
        if current and candidate_len > max_chars:
            chunk_text = "\n\n".join(current)
            chunks.append((current_start, current_start + len(chunk_text), chunk_text))
            overlap = chunk_text[-overlap_chars:].strip() if overlap_chars > 0 else ""
            current = [overlap, paragraph] if overlap else [paragraph]
            current_start = max(paragraph_start - len(overlap), 0) if overlap else paragraph_start
            current_len = len("\n\n".join(current))
        else:
            if not current:
                current_start = paragraph_start
            current.append(paragraph)
            current_len = candidate_len
        offset = paragraph_start + len(paragraph)
    if current:
        chunk_text = "\n\n".join(current)
        chunks.append((current_start, current_start + len(chunk_text), chunk_text))
    return chunks


def _parse_markdown_chunks(markdown: str, slug: str, markdown_relative: str, *, max_chars: int, overlap_chars: int) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    section_path: list[str] = []
    current_page: int | None = None
    saw_page_marker = False
    section_buffers: list[tuple[list[str], int | None, str]] = []
    buffer_lines: list[str] = []

    def flush() -> None:
        nonlocal buffer_lines
        text = "\n".join(buffer_lines).strip()
        if text:
            section_buffers.append((list(section_path), current_page, text))
        buffer_lines = []

    for line in markdown.splitlines():
        page_match = PAGE_MARKER.match(line)
        if page_match:
            flush()
            current_page = int(next(group for group in page_match.groups() if group))
            saw_page_marker = True
            continue
        heading = HEADING.match(line)
        if heading:
            flush()
            level = len(heading.group(1))
            title = heading.group(2).strip()
            section_path = section_path[: level - 1]
            section_path.append(title)
            continue
        buffer_lines.append(line)
    flush()

    chunks: list[dict[str, Any]] = []
    for section, page, text in section_buffers:
        for _, _, chunk_text in _split_paragraph_chunks(text, max_chars, overlap_chars):
            chunk_index = len(chunks) + 1
            locator = f"{markdown_relative}#{_slug_fragment(section, chunk_index)}"
            chunk = {
                "chunk_id": f"{slug}:c{chunk_index:04d}",
                "page": page,
                "section_path": section,
                "text": chunk_text,
                "char_start": 0,
                "char_end": len(chunk_text),
                "source_locator": locator,
                "support_scope": "source-text",
            }
            chunk["hash"] = _chunk_hash(chunk)
            chunks.append(chunk)
    if not saw_page_marker:
        warnings.append("page markers not found")
    return chunks, warnings


def build_paper_evidence_index(
    paper_root: Path,
    *,
    vault_path: Path | None = None,
    max_chars: int = 1200,
    overlap_chars: int = 150,
) -> dict[str, Any]:
    paper_root = paper_root.resolve()
    slug = paper_root.name
    markdown_path = resolve_mineru_markdown_path(paper_root)
    if not markdown_path.exists():
        raise FileNotFoundError(f"missing MinerU Markdown: {markdown_path}")
    metadata = _load_metadata(paper_root)
    markdown_relative = resolved_mineru_markdown_relative_path(paper_root)
    markdown = markdown_path.read_text(encoding="utf-8")
    chunks, warnings = _parse_markdown_chunks(
        markdown,
        slug,
        markdown_relative,
        max_chars=max_chars,
        overlap_chars=overlap_chars,
    )
    input_hashes = {"mineru_markdown": file_sha256(markdown_path)}
    metadata_path = paper_root / "metadata.json"
    if metadata_path.exists():
        input_hashes["metadata"] = file_sha256(metadata_path)
    index = {
        "schema_version": "epi-paper-evidence-index-v1",
        "paper_slug": slug,
        "title": metadata.get("title") or slug,
        "doi": metadata.get("doi"),
        "arxiv_id": metadata.get("arxiv_id"),
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "source_artifacts": {
            "metadata": "metadata.json",
            "paper_pdf": "paper.pdf",
            "mineru_markdown": markdown_relative,
            "mineru_tex": "mineru/paper.tex",
            "mineru_manifest": "mineru/mineru-manifest.json",
            "images": "mineru/images",
        },
        "input_hashes": input_hashes,
        "chunking": {
            "max_chars": max_chars,
            "overlap_chars": overlap_chars,
            "section_aware": True,
        },
        "chunks": chunks,
        "warnings": warnings,
    }
    write_json_atomic(paper_root / "evidence-index.json", index)
    if vault_path is not None:
        refresh_vault_evidence_index(vault_path, index)
    return index


def refresh_vault_evidence_index(vault_path: Path, paper_index: dict[str, Any]) -> dict[str, Any]:
    vault_path = vault_path.resolve()
    aggregate_path = epi_meta_root(vault_path) / "evidence-index.json"
    try:
        aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        aggregate = {"schema_version": "epi-vault-evidence-index-v1", "papers": []}
    papers = [
        item
        for item in aggregate.get("papers", [])
        if isinstance(item, dict) and item.get("paper_slug") != paper_index.get("paper_slug")
    ]
    evidence_path = raw_paper_root(vault_path, str(paper_index["paper_slug"])) / "evidence-index.json"
    papers.append(
        {
            "paper_slug": paper_index.get("paper_slug"),
            "title": paper_index.get("title"),
            "doi": paper_index.get("doi"),
            "arxiv_id": paper_index.get("arxiv_id"),
            "evidence_index": vault_relative(vault_path, evidence_path),
            "chunk_count": len(paper_index.get("chunks") or []),
            "input_hashes": paper_index.get("input_hashes") or {},
            "updated_at": paper_index.get("updated_at"),
        }
    )
    papers.sort(key=lambda item: str(item.get("paper_slug") or ""))
    aggregate = {
        "schema_version": "epi-vault-evidence-index-v1",
        "updated_at": utc_now(),
        "papers": papers,
    }
    write_json_atomic(aggregate_path, aggregate)
    return aggregate
```

- [ ] **Step 4: Run evidence-index tests and verify GREEN**

Run:

```powershell
python -m pytest tests\epi\test_evidence_index.py -q --basetemp=.pytest_tmp_epi_evidence_green
```

Expected: all evidence-index tests pass.

- [ ] **Step 5: Commit Task 4**

Run:

```powershell
git add plugins\epi\scripts\build\epi\evidence_index.py tests\epi\test_evidence_index.py
git commit -m "feat: index MinerU evidence chunks"
```

Expected: commit succeeds.

---

### Task 5: Generate Evidence Index After Parse Success

**Files:**
- Modify: `plugins/epi/scripts/build/epi/run_mineru_parse.py`
- Modify: `plugins/epi/scripts/build/epi/orchestrator.py`
- Test: `tests/epi/test_mineru_parse_adapter.py`

- [ ] **Step 1: Write failing parse integration tests**

Append to `tests/epi/test_mineru_parse_adapter.py`:

```python

def test_mineru_command_success_writes_evidence_index_and_aggregate(tmp_path):
    paper_root = _seed_paper_root(tmp_path, slug="fixture-paper")
    (paper_root / "metadata.json").write_text(
        json.dumps({"slug": "fixture-paper", "title": "Fixture Paper", "doi": "10.1000/fixture"}),
        encoding="utf-8",
    )
    command = [sys.executable, str(_write_success_command(tmp_path))]

    record = run_mineru_command(paper_root, command=command)

    evidence_index = json.loads((paper_root / "evidence-index.json").read_text(encoding="utf-8"))
    aggregate = json.loads((tmp_path / "vault" / "_epi" / "meta" / "evidence-index.json").read_text(encoding="utf-8"))
    assert record["evidence_index"]["path"] == str(paper_root / "evidence-index.json")
    assert record["evidence_index"]["chunk_count"] >= 1
    assert evidence_index["paper_slug"] == "fixture-paper"
    assert aggregate["papers"][0]["paper_slug"] == "fixture-paper"


def test_parse_paper_with_mineru_writes_evidence_index(tmp_path):
    vault = tmp_path / "vault"
    slug = "fixture-paper"
    paper_root = vault / "_epi" / "raw" / slug
    paper_root.mkdir(parents=True)
    (paper_root / "paper.pdf").write_bytes(b"%PDF-1.4\nfixture\n")
    (paper_root / "metadata.json").write_text(
        json.dumps({"slug": slug, "title": "Fixture Paper"}),
        encoding="utf-8",
    )
    command = [sys.executable, str(_write_success_command(tmp_path))]

    record = parse_paper_with_mineru(vault, slug, mineru_command=command)

    assert record["status"] == "success"
    assert (paper_root / "evidence-index.json").is_file()
    assert (vault / "_epi" / "meta" / "evidence-index.json").is_file()
```

- [ ] **Step 2: Run parse integration tests and verify RED**

Run:

```powershell
python -m pytest tests\epi\test_mineru_parse_adapter.py::test_mineru_command_success_writes_evidence_index_and_aggregate tests\epi\test_mineru_parse_adapter.py::test_parse_paper_with_mineru_writes_evidence_index -q --basetemp=.pytest_tmp_epi_parse_evidence_red
```

Expected: fail because parse success does not write evidence-index artifacts.

- [ ] **Step 3: Wire evidence index into `run_mineru_parse.py`**

Modify imports:

```python
from epi.evidence_index import build_paper_evidence_index
```

Add helper:

```python
def _vault_path_from_paper_root(paper_root: Path) -> Path | None:
    parts = paper_root.parts
    if len(parts) >= 3 and parts[-3] == "_epi" and parts[-2] == "raw":
        return Path(*parts[:-3])
    return None


def _attach_evidence_index(record: dict, paper_root: Path) -> dict:
    vault_path = _vault_path_from_paper_root(paper_root)
    try:
        evidence_index = build_paper_evidence_index(paper_root, vault_path=vault_path)
    except (FileNotFoundError, OSError, ValueError) as exc:
        record["evidence_index"] = {"status": "failed", "error": str(exc)}
        return record
    record["evidence_index"] = {
        "status": "success",
        "path": str(paper_root / "evidence-index.json"),
        "chunk_count": len(evidence_index.get("chunks") or []),
        "warnings": evidence_index.get("warnings") or [],
    }
    record.setdefault("output_artifact_hashes", {})
    record["output_artifact_hashes"]["evidence-index.json"] = file_sha256(paper_root / "evidence-index.json")
    return record
```

Before writing `parse-record.json` in successful `run_mineru_command`, add:

```python
    record = _attach_evidence_index(record, paper_root)
```

In successful `materialize_mineru_fixture`, add the same before writing `parse-record.json`.

- [ ] **Step 4: Run parse/evidence tests and verify GREEN**

Run:

```powershell
python -m pytest tests\epi\test_mineru_parse_adapter.py tests\epi\test_evidence_index.py -q --basetemp=.pytest_tmp_epi_parse_evidence_green
```

Expected: tests pass.

- [ ] **Step 5: Commit Task 5**

Run:

```powershell
git add plugins\epi\scripts\build\epi\run_mineru_parse.py tests\epi\test_mineru_parse_adapter.py
git commit -m "feat: write evidence index after MinerU parse"
```

Expected: commit succeeds.

---

### Task 6: Surface Evidence Index in Staging and Handoff

**Files:**
- Modify: `plugins/epi/scripts/build/epi/stage_wiki.py`
- Modify: `plugins/epi/scripts/build/epi/wiki_ingest_handoff.py`
- Test: `tests/epi/test_one_paper_ingest.py`
- Test: `tests/epi/test_wiki_ingest_handoff.py`

- [ ] **Step 1: Write failing staging and handoff tests**

Append to `tests/epi/test_wiki_ingest_handoff.py`:

```python

def test_wiki_ingest_handoff_exposes_evidence_index_locator(tmp_path):
    vault = tmp_path / "vault"
    slug = _seed_agent_handoff(vault)
    paper_root = vault / "_epi" / "raw" / slug
    evidence_index_path = paper_root / "evidence-index.json"
    _write_json(
        evidence_index_path,
        {
            "schema_version": "epi-paper-evidence-index-v1",
            "paper_slug": slug,
            "chunks": [{"chunk_id": f"{slug}:c0001", "text": "Fixture evidence"}],
            "input_hashes": {"mineru_markdown": "abc"},
            "warnings": [],
        },
    )
    brief_path = vault / "_epi" / "staging" / "papers" / slug / "wiki-ingest-brief.json"
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["source_bundle"]["evidence"]["full_text_evidence_index"] = "evidence-index.json"
    brief["source_bundle"]["evidence"]["full_text_chunk_count"] = 1
    brief["source_bundle"]["evidence"]["vault_evidence_index"] = "_epi/meta/evidence-index.json"
    _write_json(brief_path, brief)

    handoff = build_wiki_ingest_handoff(vault, slug)

    assert handoff["evidence_index"]["paper"] == "evidence-index.json"
    assert handoff["evidence_index"]["chunk_count"] == 1
    assert any("evidence-index.json" in item for item in handoff["agent_checklist"])
```

In `tests/epi/test_one_paper_ingest.py`, add assertion inside the existing source-staging test that reads `wiki_ingest_brief`:

```python
    assert wiki_ingest_brief["source_bundle"]["evidence"]["full_text_evidence_index"] == "evidence-index.json"
    assert wiki_ingest_brief["source_bundle"]["evidence"]["vault_evidence_index"] == "_epi/meta/evidence-index.json"
```

- [ ] **Step 2: Run staging/handoff tests and verify RED**

Run:

```powershell
python -m pytest tests\epi\test_wiki_ingest_handoff.py::test_wiki_ingest_handoff_exposes_evidence_index_locator tests\epi\test_one_paper_ingest.py -q --basetemp=.pytest_tmp_epi_handoff_red
```

Expected: fail because staging/handoff does not expose evidence-index fields yet.

- [ ] **Step 3: Add evidence-index metadata to staging brief**

In `plugins/epi/scripts/build/epi/stage_wiki.py`, add helper near `_load_evidence_map`:

```python
def _load_full_text_evidence_index(paper_root: Path) -> dict:
    path = paper_root / "evidence-index.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"status": "unreadable", "path": "evidence-index.json"}
    return {
        "status": "available",
        "path": "evidence-index.json",
        "chunk_count": len(payload.get("chunks") or []),
        "input_hashes": payload.get("input_hashes") or {},
        "warnings": payload.get("warnings") or [],
    }
```

Inside `_build_wiki_ingest_brief`, before returning, compute:

```python
    full_text_evidence_index = _load_full_text_evidence_index(paper_root)
```

Add to `source_bundle["evidence"]`:

```python
                "full_text_evidence_index": full_text_evidence_index.get("path"),
                "full_text_evidence_index_status": full_text_evidence_index.get("status", "missing"),
                "full_text_chunk_count": full_text_evidence_index.get("chunk_count", 0),
                "full_text_input_hashes": full_text_evidence_index.get("input_hashes", {}),
                "full_text_warnings": full_text_evidence_index.get("warnings", []),
                "vault_evidence_index": "_epi/meta/evidence-index.json",
```

- [ ] **Step 4: Add handoff evidence-index payload and checklist cue**

In `plugins/epi/scripts/build/epi/wiki_ingest_handoff.py`, in `build_wiki_ingest_handoff`, compute:

```python
    evidence_bundle = (
        brief.get("source_bundle", {}).get("evidence")
        if isinstance(brief.get("source_bundle"), dict)
        else {}
    )
    evidence_bundle = evidence_bundle if isinstance(evidence_bundle, dict) else {}
```

Add top-level return key:

```python
        "evidence_index": {
            "paper": evidence_bundle.get("full_text_evidence_index"),
            "vault": evidence_bundle.get("vault_evidence_index"),
            "chunk_count": evidence_bundle.get("full_text_chunk_count", 0),
            "input_hashes": evidence_bundle.get("full_text_input_hashes", {}),
            "warnings": evidence_bundle.get("full_text_warnings", []),
        },
```

In `_agent_checklist`, after evidence aids sentence, add:

```python
    full_text_evidence_index = evidence_bundle.get("full_text_evidence_index")
    if full_text_evidence_index:
        checklist.append(
            "Use full-text evidence-index locator aid "
            + str(full_text_evidence_index)
            + " to find page/section/chunk evidence, then verify important claims against MinerU Markdown, TeX, images, manifest, and paper.pdf before final prose."
        )
```

- [ ] **Step 5: Run staging/handoff tests and verify GREEN**

Run:

```powershell
python -m pytest tests\epi\test_one_paper_ingest.py tests\epi\test_wiki_ingest_handoff.py -q --basetemp=.pytest_tmp_epi_handoff_green
```

Expected: tests pass.

- [ ] **Step 6: Commit Task 6**

Run:

```powershell
git add plugins\epi\scripts\build\epi\stage_wiki.py plugins\epi\scripts\build\epi\wiki_ingest_handoff.py tests\epi\test_one_paper_ingest.py tests\epi\test_wiki_ingest_handoff.py
git commit -m "feat: expose evidence index in wiki handoff"
```

Expected: commit succeeds.

---

### Task 7: Repository Cleanup and Documentation

**Files:**
- Modify: `plugins/epi/scripts/build/epi/epi_repository.py`
- Modify: `plugins/epi/docs/epi-linkage.md`
- Modify: `plugins/epi/docs/structure.md`
- Modify: `plugins/epi/docs/workflow.md`
- Modify: `plugins/epi/skills/paper-discovery/workflows/run-discovery.md`
- Modify: `plugins/epi/skills/paper-ingest/workflows/prepare-ranked.md`
- Modify: `plugins/epi/skills/wiki-provenance/SKILL.md`
- Test: `tests/epi/test_run_lifecycle.py`
- Test: `tests/epi/test_current_docs.py`
- Test: `tests/epi/test_epi_linkage_doc.py`

- [ ] **Step 1: Write failing cleanup/docs tests**

Append to `tests/epi/test_run_lifecycle.py`:

```python

def test_repository_cleanup_does_not_remove_review_sessions(tmp_path):
    from epi.epi_repository import cleanup_epi_repository

    vault = tmp_path / "vault"
    review_dir = vault / "_epi" / "reviews" / "robotics-abc"
    review_dir.mkdir(parents=True)
    (review_dir / "state.json").write_text('{"schema_version":"epi-review-session-v1"}', encoding="utf-8")

    result = cleanup_epi_repository(vault)

    assert result["status"] == "cleaned"
    assert review_dir.is_dir()
    assert (review_dir / "state.json").is_file()
```

Append to `tests/epi/test_current_docs.py`:

```python

def test_docs_document_resumable_reviews_and_evidence_index():
    workflow = (ROOT / "plugins" / "epi" / "docs" / "workflow.md").read_text(encoding="utf-8")
    structure = (ROOT / "plugins" / "epi" / "docs" / "structure.md").read_text(encoding="utf-8")
    discovery = (
        ROOT / "plugins" / "epi" / "skills" / "paper-discovery" / "workflows" / "run-discovery.md"
    ).read_text(encoding="utf-8")
    ingest = (
        ROOT / "plugins" / "epi" / "skills" / "paper-ingest" / "workflows" / "prepare-ranked.md"
    ).read_text(encoding="utf-8")
    provenance = (
        ROOT / "plugins" / "epi" / "skills" / "wiki-provenance" / "SKILL.md"
    ).read_text(encoding="utf-8")
    combined = "\n".join([workflow, structure, discovery, ingest, provenance])
    assert "_epi/reviews" in combined
    assert "default resume" in combined or "默认自动 resume" in combined
    assert "--refresh" in combined
    assert "evidence-index.json" in combined
    assert "_epi/meta/evidence-index.json" in combined
```

Append to `tests/epi/test_epi_linkage_doc.py`:

```python

def test_epi_linkage_documents_review_sessions_and_evidence_index():
    text = EPI_LINKAGE.read_text(encoding="utf-8")
    assert "_epi/reviews/<review-id>/" in text
    assert "candidates.json" in text
    assert "shortlist.json" in text
    assert "fetch_plan.json" in text
    assert "coverage.json" in text
    assert "_epi/raw/<slug>/evidence-index.json" in text
    assert "_epi/meta/evidence-index.json" in text
```

- [ ] **Step 2: Run cleanup/docs tests and verify RED**

Run:

```powershell
python -m pytest tests\epi\test_run_lifecycle.py::test_repository_cleanup_does_not_remove_review_sessions tests\epi\test_current_docs.py::test_docs_document_resumable_reviews_and_evidence_index tests\epi\test_epi_linkage_doc.py::test_epi_linkage_documents_review_sessions_and_evidence_index -q --basetemp=.pytest_tmp_epi_docs_red
```

Expected: docs tests fail until docs are updated. Cleanup test may already pass; if so, keep it as regression proof.

- [ ] **Step 3: Update EPI docs**

Make the following exact documentation additions:

In `plugins/epi/docs/epi-linkage.md`, add a section under the dry-run/discovery contract:

```markdown
### Review Sessions And Default Resume

`dry-run` now writes both `_epi/runs/<run-id>/` and `_epi/reviews/<review-id>/`. `_epi/runs` remains the single-invocation evidence record; `_epi/reviews` is the long-lived literature collection state. A repeated `dry-run --query "<topic>"` with the same normalized query, query plan, source routing, profile, filters, ranking inputs, and EasyScholar setting resumes by default from the matching review session and skips provider calls. Use `--refresh` to force a new provider search and update the review session. Use `--no-resume` only for debugging.

Each review session stores `state.json`, `query-plan.json`, `candidates.json`, `shortlist.json`, `fetch_plan.json`, `coverage.json`, and `provider-cache/query-*.json`. These files prevent context compaction or terminal interruption from causing repeated provider requests.
```

Add under source-staging/wiki provenance:

```markdown
### Full-Text Evidence Index

After MinerU parse success, EPI writes `_epi/raw/<slug>/evidence-index.json` and updates `_epi/meta/evidence-index.json`. The per-paper index stores page/section/chunk locators, chunk hashes, source artifact hashes, and warnings. It is a locator aid for claim support and wiki provenance; it does not replace `paper.pdf`, MinerU Markdown/TeX/images/manifest, or final source review.
```

In `plugins/epi/docs/structure.md`, document `review_sessions.py`, `fetch_plan.py`, `evidence_index.py`, `_epi/reviews`, and `_epi/meta/evidence-index.json`.

In `plugins/epi/docs/workflow.md`, document default resume and `--refresh`.

In `plugins/epi/skills/paper-discovery/workflows/run-discovery.md`, update Safety Boundary from "writes only `_epi/runs`" to "writes `_epi/runs` and resumable `_epi/reviews`; does not acquire PDFs..."

In `plugins/epi/skills/paper-ingest/workflows/prepare-ranked.md`, add `evidence-index.json` to optional/locator artifacts and explain it is generated after MinerU parse success.

In `plugins/epi/skills/wiki-provenance/SKILL.md`, add `evidence-index.json` and `_epi/meta/evidence-index.json` to Inputs and clarify that evidence index locators must be verified against source artifacts before final prose.

- [ ] **Step 4: Ensure cleanup policy does not target reviews**

Inspect `plugins/epi/scripts/build/epi/epi_repository.py`. If cleanup code never targets `_epi/reviews`, no code change is required. If any generic lifecycle cleanup touches all child directories under `_epi`, add an explicit skip for `reviews`.

- [ ] **Step 5: Run cleanup/docs tests and verify GREEN**

Run:

```powershell
python -m pytest tests\epi\test_run_lifecycle.py tests\epi\test_current_docs.py tests\epi\test_epi_linkage_doc.py -q --basetemp=.pytest_tmp_epi_docs_green
```

Expected: tests pass.

- [ ] **Step 6: Commit Task 7**

Run:

```powershell
git add plugins\epi\scripts\build\epi\epi_repository.py plugins\epi\docs\epi-linkage.md plugins\epi\docs\structure.md plugins\epi\docs\workflow.md plugins\epi\skills\paper-discovery\workflows\run-discovery.md plugins\epi\skills\paper-ingest\workflows\prepare-ranked.md plugins\epi\skills\wiki-provenance\SKILL.md tests\epi\test_run_lifecycle.py tests\epi\test_current_docs.py tests\epi\test_epi_linkage_doc.py
git commit -m "docs: document resumable reviews and evidence index"
```

Expected: commit succeeds. If `epi_repository.py` did not need changes, omit it from `git add`.

---

### Task 8: Final Regression and Acceptance

**Files:**
- No new files expected, but fixes may touch files from earlier tasks.

- [ ] **Step 1: Run focused feature tests**

Run:

```powershell
python -m pytest tests\epi\test_review_sessions.py tests\epi\test_orchestrator_dry_run.py tests\epi\test_cli_parser.py tests\epi\test_evidence_index.py tests\epi\test_mineru_parse_adapter.py tests\epi\test_one_paper_ingest.py tests\epi\test_wiki_ingest_handoff.py tests\epi\test_run_lifecycle.py tests\epi\test_current_docs.py tests\epi\test_epi_linkage_doc.py -q --basetemp=.pytest_tmp_epi_resume_focused
```

Expected: all focused tests pass.

- [ ] **Step 2: Run full EPI test suite**

Run:

```powershell
python -m pytest tests\epi plugins\epi\tests -q --basetemp=.pytest_tmp_epi_resume_full
```

Expected: all EPI tests pass.

- [ ] **Step 3: Inspect generated artifact names for spec compliance**

Run:

```powershell
rg -n "_epi/reviews|candidates.json|shortlist.json|fetch_plan.json|coverage.json|evidence-index.json|provider_call_skipped|--refresh|--no-resume" plugins\epi tests\epi docs\superpowers\specs\2026-06-06-epi-resumable-review-evidence-index-design.md
```

Expected: all named artifacts and flags appear in implementation, tests, and docs.

- [ ] **Step 4: Check no secrets are written**

Run:

```powershell
rg -n "SECRET_KEY|PAPER_SEARCH_MCP_.*KEY|TOKEN" plugins\epi\scripts\build\epi\review_sessions.py plugins\epi\scripts\build\epi\evidence_index.py tests\epi\test_review_sessions.py tests\epi\test_evidence_index.py
```

Expected: no secret-writing logic. It is acceptable if only test text refers to field names; review actual hits before proceeding.

- [ ] **Step 5: Check worktree status**

Run:

```powershell
git status --short
git log --oneline -8
```

Expected: clean worktree and recent commits for Tasks 1-7.

- [ ] **Step 6: Commit any final fixes**

If Step 1 or Step 2 required fixes, commit them:

```powershell
git add <changed-files>
git commit -m "test: cover EPI resumable review workflow"
```

Expected: no uncommitted feature changes remain.

- [ ] **Step 7: Summarize acceptance evidence**

Prepare a concise completion note with:

- Worktree path and branch.
- Commit list.
- Focused and full test commands with pass/fail counts.
- Explicit statement that default `dry-run` resumes and `--refresh` forces provider calls.
- Explicit statement that MinerU parse writes per-paper and aggregate evidence indexes.
- Any known limitations, especially that semantic evidence-query CLI is a future batch.

---

## Self-Review Against Spec

- Default resume: Task 3 covers matching review session lookup, provider-call skip, new run creation, and report/run-state metadata.
- `--refresh`: Task 2 adds CLI flag, Task 3 forces provider call and refresh metadata.
- Persistent state artifacts: Task 1 creates `state.json`, `query-plan.json`, `candidates.json`, `shortlist.json`, `fetch_plan.json`, `coverage.json`, `provider-cache`.
- Partial resume: Task 1 covers provider-cache-only rehydration.
- `_epi/runs` remains execution evidence: Task 3 writes new run every invocation.
- Evidence index: Tasks 4 and 5 create per-paper and aggregate indexes.
- Handoff exposure: Task 6 adds staging and handoff surface.
- Docs: Task 7 updates public docs and skill guidance.
- Tests: Tasks 1-8 add focused unit/integration/regression tests and full-suite verification.
- Non-goal preserved: no semantic/vector evidence query is implemented; Task 8 reports this as a future batch.
