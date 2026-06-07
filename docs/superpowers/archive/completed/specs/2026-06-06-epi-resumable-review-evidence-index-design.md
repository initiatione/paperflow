# EPI Resumable Review State and Evidence Index Design

## Summary

EPI will add a persistent review-session layer for literature collection and a full-text evidence index for parsed papers.

The review-session layer makes `dry-run --query ...` resumable by default. A matching review session reuses cached provider results and persisted candidate state instead of calling paper-search providers again. `--refresh` is the explicit escape hatch for a new provider search.

The evidence-index layer turns MinerU output into local, source-addressable chunks. Each parsed paper gets a per-paper index, and the vault gets an aggregate index that wiki handoffs can expose. This improves claim-to-source provenance and enables future "find papers supporting this claim" workflows.

## Current Problem

Current discovery creates a new `_epi/runs/<run-id>/` directory on every `dry-run` and calls `discover()` before any reusable state is checked. `_epi/runs` is an execution log and is subject to lifecycle cleanup, so it is the wrong source of truth for long-lived literature-review state.

The practical failure mode is:

1. An agent starts a paper search.
2. The terminal exits, the conversation is compacted, or the user resumes later.
3. The next agent only sees the request or a prior run id.
4. `dry-run` calls providers again, wasting time, tokens, and provider quota.

For evidence, current fast ingest preserves `paper.pdf`, `metadata.json`, MinerU Markdown/TeX/images/manifest, and optional reader sidecars. That is source-first, but there is no unified page/section/chunk index that can be queried or surfaced as a reusable evidence route.

## Goals

- Make `dry-run --query ...` resume matching literature-collection state by default.
- Avoid repeated provider calls after interruption, compaction, or terminal restart.
- Keep `_epi/runs` as immutable single-execution evidence, not long-lived review state.
- Add `_epi/reviews/<review-id>/` as the long-lived review-session source of truth.
- Persist `candidates.json`, `shortlist.json`, `fetch_plan.json`, and `coverage.json`.
- Persist enough query and provider-cache state to resume after partial completion.
- Add `--refresh` to force a new provider search for the same topic/signature.
- Preserve a new `_epi/runs/<run-id>/` report for every user-visible `dry-run`, including resumed runs.
- Generate per-paper full-text evidence indexes after MinerU parse success.
- Maintain a vault-level aggregate evidence index for later claim lookup.
- Expose evidence-index paths in source-staging and wiki-ingest handoff artifacts.
- Keep final wiki provenance conservative: the index is a locator aid, not source authority.

## Non-Goals

- Do not replace `paper.pdf`, MinerU Markdown, TeX, images, or manifest as source artifacts.
- Do not make full-text evidence ranking an LLM or embedding requirement in this batch.
- Do not implement a full semantic vector database in this batch.
- Do not auto-write final wiki pages from evidence-index chunks.
- Do not store secrets, provider tokens, or raw environment values in review sessions.
- Do not remove `_epi/runs`; each run still records what happened in that invocation.
- Do not rely on `_epi/runs` for resume correctness because run lifecycle cleanup may delete old runs.
- Do not change installed plugin cache behavior in this source-design step.

## External Patterns Used

The implementation borrows patterns, not dependencies:

- PaperQA2: local indexes are reused on later queries, and full-text chunks are treated as evidence contexts.
- ASReview LAB: review projects keep persistent screening state and decisions instead of treating each screen as a stateless run.
- ai-skill-scholar: literature reviews are self-contained directories with `state.json`, `candidates.json`, `shortlist.json`, and `fetch_plan.json`.

EPI will keep its own artifact layout, source-first wiki boundary, and provider adapter contracts.

## Source-of-Truth Model

### Execution Runs

`_epi/runs/<run-id>/` remains the single-invocation record.

It records:

- command inputs
- `query-plan.json`
- `search-record.json`
- `normalized.json`
- `filter-report.json`
- `easyscholar-record.json`
- `rank.json`
- `report.md`
- `report.json`
- `run-state.json`

Runs answer "what happened this time?"

### Review Sessions

`_epi/reviews/<review-id>/` becomes the long-lived literature collection state.

It records:

- normalized topic/config signature
- provider result cache
- candidate pool
- screening/ranking state
- fetch plan
- coverage information
- links to runs that observed or refreshed the session

Review sessions answer "what is the current state of this literature collection task?"

### Raw Paper Evidence

`_epi/raw/<slug>/evidence-index.json` becomes the per-paper full-text locator index.

It records:

- source artifact paths
- MinerU Markdown identity and hash
- page/section/chunk text locators
- chunk hashes
- parse warnings

Raw paper indexes answer "where in this paper is evidence located?"

### Aggregate Evidence Index

`_epi/meta/evidence-index.json` becomes the vault-level catalog of per-paper evidence indexes.

It records:

- paper slug
- title and stable identifiers when available
- evidence-index path
- source artifact hashes
- chunk count
- last indexed time

The aggregate index answers "which indexed papers can be searched for evidence?"

## Review Session Layout

Each session directory uses this layout:

```text
_epi/reviews/<review-id>/
  state.json
  query-plan.json
  candidates.json
  shortlist.json
  fetch_plan.json
  coverage.json
  provider-cache/
    query-01.json
    query-02.json
    query-03.json
  runs/
    <run-id>.json
```

The `review-id` is deterministic enough for discoverability but not the cache key. The cache key is the signature in `state.json`.

Recommended format:

```text
<topic-slug>-<signature-prefix>
```

The signature prefix is the first 12 hex characters of the review signature.

## Review Signature

The review signature prevents unsafe reuse between different search intents.

It includes:

- normalized query text
- exact lookup mode, if any
- query-plan enabled flag
- query-plan domain
- query-plan max query count
- query variants
- requested sources
- selected sources
- source routing policy
- `max_results`
- vault profile
- configured domains
- positive keywords
- negative keywords
- venue prior
- default exclusion terms
- existing-library dedupe policy version
- ranking/filter schema versions
- EasyScholar enabled flag

It excludes:

- timestamps
- run id
- provider readiness status that only says whether an env var is currently set
- secret values
- absolute plugin path

Provider readiness is recorded in `coverage.json`, but it should not by itself force a new review session. A missing or newly configured provider is a reason for `--refresh`, not an accidental signature drift.

## Review State Schema

`state.json`:

```json
{
  "schema_version": "epi-review-session-v1",
  "review_id": "topic-slug-123456789abc",
  "topic": "original user query",
  "normalized_topic": "normalized user query",
  "signature": "sha256...",
  "signature_inputs_path": "signature-inputs.json",
  "status": "active",
  "phase": "ranked",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601",
  "last_run_id": "20260606T...",
  "run_ids": ["20260606T..."],
  "resume_count": 2,
  "refresh_count": 0,
  "candidate_counts": {
    "raw": 0,
    "normalized": 0,
    "filtered": 0,
    "ranked": 0,
    "accepted": 0,
    "rejected": 0
  },
  "artifacts": {
    "query_plan": "query-plan.json",
    "candidates": "candidates.json",
    "shortlist": "shortlist.json",
    "fetch_plan": "fetch_plan.json",
    "coverage": "coverage.json"
  }
}
```

Valid phases:

- `initialized`
- `planned`
- `searched`
- `normalized`
- `filtered`
- `quality_enriched`
- `ranked`
- `fetch_planned`
- `stale`
- `failed`

`active` sessions are reusable. `stale` sessions are visible but not default-resumed. A session becomes stale only when a schema version or explicit invalidation rule requires it.

## Candidate and Shortlist Artifacts

`candidates.json` stores the discovery candidate pool:

```json
{
  "schema_version": "epi-review-candidates-v1",
  "review_id": "topic-slug-123456789abc",
  "records": [],
  "normalized": [],
  "source_record_paths": [
    "provider-cache/query-01.json"
  ],
  "record_count": 0,
  "normalized_count": 0
}
```

`shortlist.json` stores filtering, enrichment, and ranking output:

```json
{
  "schema_version": "epi-review-shortlist-v1",
  "review_id": "topic-slug-123456789abc",
  "kept": [],
  "rejected": [],
  "ranked_pool": [],
  "accepted": [],
  "filter_report_path": null,
  "easyscholar_record_path": null
}
```

The accepted list mirrors the run-level `rank.json` entries. Run-level `rank.json` remains the artifact consumed by `prepare-ranked --run-id`.

## Fetch Plan Artifact

`fetch_plan.json` is the bridge from review state to acquisition.

It records:

- candidate slug
- title
- DOI
- arXiv id
- candidate PDF URLs
- alternate PDF URLs
- source identities for MCP download
- manual-download fallback links
- recommended acquisition order
- known blockers from prior attempts, if any

It does not download anything. It is a plan and resume aid.

`prepare-ranked` may keep using `rank.json` as its required input. This batch should make the fetch plan visible and future-compatible without forcing a new prepare command shape.

## Coverage Artifact

`coverage.json` stores source coverage and recall diagnostics:

```json
{
  "schema_version": "epi-review-coverage-v1",
  "review_id": "topic-slug-123456789abc",
  "query_count": 0,
  "sources_used": [],
  "source_results": {},
  "errors": {},
  "raw_total": 0,
  "deduped_total": 0,
  "capabilities": {},
  "provider_readiness": {},
  "source_routing": {},
  "query_records": [],
  "warnings": []
}
```

It is copied or referenced in each resumed run's `report.json.discovery_context.source_coverage`.

## Provider Cache

Each provider-cache record is one provider search call or one query variant result:

```json
{
  "schema_version": "epi-provider-cache-record-v1",
  "review_id": "topic-slug-123456789abc",
  "query_index": 1,
  "query": "query variant",
  "sources": ["arxiv", "semantic"],
  "source_mode": "paper-search-mcp",
  "records": [],
  "upstream": {},
  "error": null,
  "warnings": [],
  "created_at": "ISO-8601",
  "provider_call": {
    "called": true,
    "reason": "refresh_or_cache_miss"
  }
}
```

On resume, EPI reads these files and rebuilds the same search-record shape expected by the existing normalize/filter/rank path. The run-level `search-record.json` marks:

```json
{
  "resumed": true,
  "resumed_from_review_id": "topic-slug-123456789abc",
  "provider_call_skipped": true
}
```

## Default Resume Behavior

Default `dry-run` behavior:

1. Build config and source routing as current code does.
2. Build query plan when enabled.
3. Compute review signature.
4. Find an active review with the same signature.
5. If found and `--refresh` is not set, resume from `_epi/reviews/<review-id>/`.
6. Create a new `_epi/runs/<run-id>/` for this invocation.
7. Rehydrate search/candidate/ranking artifacts into the run directory.
8. Write report and run-state with resume metadata.
9. Do not call paper-search providers.

Refresh behavior:

1. `dry-run --refresh` bypasses provider cache.
2. It calls providers and writes fresh provider-cache records.
3. It updates the matching review session when the signature is the same.
4. It increments `refresh_count`.
5. It creates a new run that records `refresh: true`.

If no matching review exists, `dry-run` behaves like today but also writes the new review session.

## Partial Resume Behavior

The session should resume from the most advanced valid phase.

Examples:

- `provider-cache` exists but `candidates.json` is missing: rebuild candidates from provider-cache without provider calls.
- `candidates.json` exists but `shortlist.json` is missing: rerun filter, EasyScholar enrichment, and ranking.
- `shortlist.json` exists: copy accepted ranked candidates into the new run and write report.
- `coverage.json` is missing but provider-cache exists: rebuild coverage from provider-cache.

This is the key behavior for terminal interruptions.

If an artifact is malformed JSON, mark the session `failed` or `stale` and require `--refresh`. Do not silently mix corrupt cached state with new provider output.

## CLI Changes

Add to `dry-run`:

```powershell
python scripts\orchestrator.py dry-run --query "<topic>" --vault <vault>
python scripts\orchestrator.py dry-run --query "<topic>" --vault <vault> --refresh
python scripts\orchestrator.py dry-run --query "<topic>" --vault <vault> --no-resume
```

`--refresh` forces provider calls and updates review state.

`--no-resume` is a debug escape hatch. It creates a normal run without reading a review session, but it should not be advertised as the default workflow. If both `--refresh` and `--no-resume` are supplied, parser validation should reject the command because the meanings conflict.

The JSON output from `dry-run --json` adds:

```json
{
  "review": {
    "review_id": "topic-slug-123456789abc",
    "review_dir": "_epi/reviews/topic-slug-123456789abc",
    "resumed": true,
    "refreshed": false,
    "provider_call_skipped": true,
    "artifacts": {
      "state": ".../state.json",
      "candidates": ".../candidates.json",
      "shortlist": ".../shortlist.json",
      "fetch_plan": ".../fetch_plan.json",
      "coverage": ".../coverage.json"
    }
  }
}
```

## Report Changes

`report.json.discovery_context` gains:

```json
{
  "review_session": {
    "review_id": "topic-slug-123456789abc",
    "review_dir": "...",
    "resumed": true,
    "refreshed": false,
    "provider_call_skipped": true,
    "resume_reason": "matching_signature"
  }
}
```

`report.md` gains a compact Review Session section:

```text
## Review Session

- review_id: topic-slug-123456789abc
- resumed: true
- provider_call_skipped: true
- refresh: false
- candidates: _epi/reviews/.../candidates.json
- shortlist: _epi/reviews/.../shortlist.json
- fetch_plan: _epi/reviews/.../fetch_plan.json
- coverage: _epi/reviews/.../coverage.json
```

## Evidence Index Layout

Per-paper:

```text
_epi/raw/<slug>/evidence-index.json
```

Aggregate:

```text
_epi/meta/evidence-index.json
```

The aggregate index should be updated after each successful per-paper evidence index write. It should use atomic writes.

## Evidence Index Schema

Per-paper index:

```json
{
  "schema_version": "epi-paper-evidence-index-v1",
  "paper_slug": "paper-slug",
  "title": "Paper title",
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601",
  "source_artifacts": {
    "metadata": "metadata.json",
    "paper_pdf": "paper.pdf",
    "mineru_markdown": "mineru/paper-slug.md",
    "mineru_tex": "mineru/paper.tex",
    "mineru_manifest": "mineru/mineru-manifest.json",
    "images": "mineru/images"
  },
  "input_hashes": {
    "mineru_markdown": "sha256...",
    "metadata": "sha256..."
  },
  "chunking": {
    "max_chars": 1200,
    "overlap_chars": 150,
    "section_aware": true
  },
  "chunks": [
    {
      "chunk_id": "paper-slug:c0001",
      "page": 1,
      "section_path": ["Introduction"],
      "text": "chunk text",
      "char_start": 0,
      "char_end": 1000,
      "source_locator": "mineru/paper-slug.md#introduction:c0001",
      "support_scope": "source-text",
      "hash": "sha256..."
    }
  ],
  "warnings": []
}
```

Aggregate index:

```json
{
  "schema_version": "epi-vault-evidence-index-v1",
  "updated_at": "ISO-8601",
  "papers": [
    {
      "paper_slug": "paper-slug",
      "title": "Paper title",
      "doi": "10...",
      "arxiv_id": null,
      "evidence_index": "_epi/raw/paper-slug/evidence-index.json",
      "chunk_count": 42,
      "input_hashes": {},
      "updated_at": "ISO-8601"
    }
  ]
}
```

## Chunking Rules

The first implementation should be deterministic and dependency-light.

Rules:

- Parse MinerU Markdown headings into a `section_path`.
- Preserve heading context for each chunk.
- Use page markers when MinerU emits them.
- If page markers are absent, set `page` to `null` and preserve Markdown locator.
- Split long sections into chunks by paragraph boundaries when possible.
- Use a fixed max character budget and small overlap.
- Hash chunk text and locator fields for drift detection.
- Skip image-only chunks unless MinerU Markdown has useful text around the image.

The index should prefer stable locators over perfect page detection. If page extraction is uncertain, record a warning instead of inventing a page number.

## Evidence Index Generation Points

Generate or refresh the per-paper evidence index after MinerU parse success in:

- `parse-paper`
- `advance-paper`
- `advance-ranked`
- `prepare-ranked`
- `ingest-one`
- `redo-parse`

If a parse step fails, do not write a successful evidence index. Existing indexes should remain but aggregate entries should indicate stale input hashes if the source Markdown changed.

## Handoff and Wiki Provenance Integration

Source-staging and handoff artifacts should expose:

- per-paper `evidence-index.json`
- aggregate `_epi/meta/evidence-index.json`
- chunk count
- input hashes
- evidence-index warnings

`wiki-ingest-handoff` should add evidence index paths to the agent checklist as locator aids:

- use evidence index for finding source-grounded passages
- verify important claims against source artifacts before final prose
- preserve support status in final pages

The evidence index does not upgrade a claim to `verified`. Verification still requires source reread, formula/figure review, and final-source-review recording.

## Querying Evidence

This design only requires index generation and exposure. A future batch can add:

```powershell
python scripts\orchestrator.py evidence-query --claim "<claim>" --vault <vault>
python scripts\orchestrator.py evidence-query --paper <slug> --claim "<claim>" --vault <vault>
```

This batch should structure the data so that future command can search chunks without reparsing every paper.

## Error Handling

Review sessions:

- Corrupt JSON: mark the session failed or stale and require `--refresh`.
- Signature mismatch: create or use a different session.
- Provider-cache missing but candidates exist: resume from candidates.
- Candidates missing but provider-cache exists: rebuild candidates without provider calls.
- No reusable state: call providers normally and create a session.

Evidence indexes:

- Missing MinerU Markdown: do not write an index; record a parse/staging warning.
- Malformed metadata: index chunks but omit unavailable identifiers.
- Ambiguous page numbers: set `page` to `null` and record a warning.
- Empty Markdown: write a failed index record only if useful for diagnostics; do not add it to aggregate as searchable.

## Backward Compatibility

Existing run directories remain valid.

Existing `prepare-ranked --run-id <dry-run-id>` continues to read run-level `rank.json`.

Existing source-staging and wiki handoff contracts remain source-first. They gain additional evidence-index paths but do not lose required source artifact checks.

Existing `_epi/runs` lifecycle cleanup remains valid because review sessions are stored under `_epi/reviews`.

Repository cleanup policies must not delete active review sessions by default.

## Documentation Updates

Implementation must update:

- `plugins/epi/docs/epi-linkage.md`
- `plugins/epi/docs/structure.md`
- `plugins/epi/docs/workflow.md`
- `plugins/epi/skills/paper-discovery/workflows/run-discovery.md`
- `plugins/epi/skills/paper-ingest/workflows/prepare-ranked.md`
- `plugins/epi/skills/wiki-provenance/SKILL.md` or its references if handoff wording changes materially

The docs must explicitly say that `dry-run` now writes `_epi/runs` and `_epi/reviews` by default.

## Testing Plan

Add focused tests under `plugins/epi/tests`.

Review-session tests:

- First dry-run with fixture/provider stub creates `_epi/reviews/<review-id>/state.json`.
- First dry-run writes `candidates.json`, `shortlist.json`, `fetch_plan.json`, and `coverage.json`.
- Second dry-run with the same signature resumes and does not call provider.
- Resumed run still writes a new `_epi/runs/<run-id>/`.
- Resumed run report records `provider_call_skipped=true`.
- `--refresh` bypasses cache and calls provider again.
- Partial state with provider-cache but no candidates rebuilds candidates without provider calls.
- Corrupt session artifact requires refresh instead of silently mixing state.

Evidence-index tests:

- MinerU Markdown fixture with headings creates section-aware chunks.
- Markdown fixture with page markers records page locators.
- Markdown fixture without page markers records `page=null` and warning only when appropriate.
- Evidence index writes input hashes and stable chunk hashes.
- Aggregate `_epi/meta/evidence-index.json` updates after per-paper index write.
- `prepare-ranked` or parse success path exposes evidence-index paths in staging/handoff artifacts.

Regression tests:

- Existing dry-run report fields remain present.
- Existing `prepare-ranked --run-id` still consumes run-level `rank.json`.
- Run lifecycle cleanup does not delete `_epi/reviews`.
- Secret values are not present in review or evidence artifacts.

## Acceptance Criteria

- A repeated `dry-run --query ...` with unchanged signature resumes by default.
- The repeated run skips provider calls and records that skip in run-state/report JSON.
- `dry-run --refresh` forces provider calls and updates review state.
- Review state persists outside `_epi/runs`.
- Interrupted discovery can resume from the most advanced valid review phase.
- Review artifacts include `candidates.json`, `shortlist.json`, `fetch_plan.json`, and `coverage.json`.
- MinerU parse success writes `_epi/raw/<slug>/evidence-index.json`.
- The vault aggregate `_epi/meta/evidence-index.json` records indexed papers.
- Wiki handoff exposes evidence-index paths as source locator aids.
- Tests cover resume, refresh, partial resume, evidence index generation, aggregate update, and handoff exposure.

## Open Implementation Boundaries

The implementation should prefer small modules instead of expanding `orchestrator.py`:

- `review_sessions.py` for signatures, session lookup, state writes, and provider-cache rehydration.
- `fetch_plan.py` for fetch-plan construction from ranked candidates.
- `evidence_index.py` for MinerU Markdown chunking and aggregate updates.
- Narrow orchestrator changes to call these modules at existing stage boundaries.

These boundaries are part of the design, not optional refactoring, because this feature spans discovery, ingest, and wiki handoff.
