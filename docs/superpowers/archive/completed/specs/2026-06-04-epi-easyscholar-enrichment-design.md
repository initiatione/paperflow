# EPI EasyScholar Enrichment Design

## Summary

EPI will add a default-on EasyScholar quality enrichment layer to improve paper quality screening during discovery. The feature is based on the MIT-licensed `chaosman42/easyscholar-mcp` project, but EPI will port the core EasyScholar API integration into a native Python module instead of launching the upstream Node MCP server as a nested process.

The enrichment layer runs inside `dry-run` after candidate normalization/filtering and before ranking:

```text
paper-search -> normalize -> filter -> easyscholar_enrich -> rank -> report
```

The integration is an evidence signal, not a replacement for EPI's existing quality model. EasyScholar can raise venue/source confidence when it verifies journal or conference quality metrics, but it cannot by itself make an off-topic or weakly evidenced paper Tier A.

## Goals

- Reuse and credit the EasyScholar API integration pattern from `chaosman42/easyscholar-mcp`.
- Query EasyScholar by publication or venue name for filtered EPI candidates.
- Add verified venue metrics to each enriched candidate.
- Improve ranking and quality gates using bounded EasyScholar-derived signals.
- Keep `dry-run` default-on for EasyScholar when credentials are available.
- Preserve full discovery behavior when credentials are missing or the API fails.
- Avoid writing or printing EasyScholar secrets in repo, vault, reports, or logs.
- Record provenance, cache usage, failures, and unverifiable metrics in run artifacts.

## Non-Goals

- Do not embed the upstream Node MCP server or add a required Node runtime for EPI discovery.
- Do not make EasyScholar a hard dependency for paper discovery.
- Do not treat journal metrics as scholarly truth or peer review.
- Do not invent impact factors, quartiles, rankings, acceptance rates, or citation counts.
- Do not let venue quality override topic fit, PDF availability, stable identity, or evidence checks.
- Do not store `EASYSCHOLAR_SECRET_KEY` in `_epi` artifacts, git-tracked files, or generated reports.

## Upstream Reuse

The upstream `chaosman42/easyscholar-mcp` repository provides:

- API base: `https://www.easyscholar.cc/open`
- Endpoint: `/getPublicationRank`
- Required query fields: `secretKey` and `publicationName`
- Environment secret convention: `EASYSCHOLAR_SECRET_KEY`
- Tool semantics:
  - `get_publication_rank` for formatted output
  - `get_publication_rank_raw` for raw JSON
- Result structure centered on `data.officialRank.all` and `data.officialRank.select`
- Supported systems including JCR quartile, CAS zone, impact factor, 5-year impact factor, JCI, ABDC, AJG, FT50, UTD24, FMS, CCF, PKU Core, CSSCI, CSCD, EI, ESI, and university-specific rankings.

EPI will port the API call, result interpretation, and broad field coverage into Python. EPI will not copy the MCP transport layer because EPI already has its own CLI, run artifacts, doctor checks, runtime config, and ranking pipeline.

The MIT attribution will be recorded in `plugins/epi/docs/attribution.md` and, if code is adapted closely enough to warrant it, in a vendor notice under `plugins/epi/vendor-notices/easyscholar-mcp.md`.

## Configuration

EasyScholar is default-on for `dry-run`.

Runtime secret handling:

- Primary secret source: `EASYSCHOLAR_SECRET_KEY` process environment variable.
- Optional env-file source: a runtime-configured env file may set `EASYSCHOLAR_SECRET_KEY`.
- `doctor` and `config-status --include-runtime` may report only `set` or `missing`.
- Reports, run-state files, cache records, and logs must not contain the secret.

Vault config default:

```yaml
quality_enrichment:
  easyscholar:
    enabled: true
    timeout_seconds: 15
    cache_ttl_days: 30
    max_candidates_per_run: 50
```

CLI behavior:

- `python scripts\orchestrator.py dry-run ...` uses EasyScholar enrichment by default.
- `--no-easyscholar` disables enrichment for a single dry-run.
- Fixture tests can disable live network calls either with `--no-easyscholar` or by monkeypatching the EasyScholar client.

Runtime config behavior:

- The user-level runtime config may set `EPI_*` controls as before.
- It may also load env files containing `EASYSCHOLAR_SECRET_KEY`, using the same safe reporting style as MinerU.
- Explicit process environment variables take precedence over runtime config.

## Data Flow

After filtering, EPI will collect publication names from each candidate. The main source is `candidate["venue"]`; fallback sources may include normalized raw record fields such as `publication_venue`, `journal`, `conference`, and `container_title` when present.

For each candidate:

1. Skip if no usable publication name exists.
2. Normalize the publication name for cache lookup.
3. Load a fresh cache entry when available.
4. Query EasyScholar when no fresh cache entry exists and the secret is set.
5. Parse the raw response into EPI's stable quality metrics schema.
6. Attach enrichment fields to the candidate.

Run-level artifact:

```text
<vault>\_epi\runs\<run-id>\easyscholar-record.json
```

Candidate-level fields:

```json
{
  "verified_metrics": {
    "easyscholar": {
      "status": "matched",
      "publication_name": "Example Journal",
      "source": "easyscholar",
      "metrics": {
        "jcr_quartile": "Q1",
        "cas_zone_upgraded": "1",
        "impact_factor": "9.4",
        "five_year_impact_factor": "11.2",
        "jci": "1.8",
        "ccf": "A",
        "abdc": "A*",
        "ajg": "4*",
        "ei": "Yes",
        "esi_subject": "Engineering"
      },
      "warnings": []
    }
  },
  "quality_signals": {
    "easyscholar": {
      "score": 0.95,
      "evidence": ["JCR Q1", "CAS 1", "impact_factor:9.4"],
      "cautions": []
    }
  },
  "easyscholar_status": "matched"
}
```

Allowed `easyscholar_status` values:

- `matched`
- `disabled`
- `missing_key`
- `no_publication_name`
- `no_match`
- `cache_hit`
- `api_error`
- `timeout`
- `invalid_response`

When the record comes from cache, the candidate can use `easyscholar_status=cache_hit` while `verified_metrics.easyscholar.status` remains `matched` or the cached failure status.

## Caching

Cache root:

```text
<vault>\_epi\cache\easyscholar\
```

Cache key:

- Lowercase publication name.
- Collapse whitespace.
- Remove punctuation that does not affect venue identity.
- Hash the normalized name to avoid unsafe filenames.

Cache payload:

```json
{
  "schema_version": "epi-easyscholar-cache-v1",
  "publication_name": "Example Journal",
  "normalized_publication_name": "example journal",
  "queried_at": "2026-06-04T00:00:00Z",
  "expires_at": "2026-07-04T00:00:00Z",
  "status": "matched",
  "raw_response": {},
  "parsed_metrics": {},
  "error": null
}
```

The cache records raw EasyScholar responses for auditability, but never records `secretKey`.

## Ranking Integration

`rank_papers.py` will consume EasyScholar-enriched candidate fields.

New ranking signal:

```json
{
  "easyscholar_score": 0.0
}
```

Signal mapping principles:

- JCR Q1, CAS 1, CCF A, ABDC A*, ABDC A, AJG 4*, AJG 4, FT50, UTD24, and high impact factor increase the score.
- JCR Q2, CAS 2, CCF B, ABDC B, AJG 3, EI, CSSCI, PKU Core, CSCD, and moderate impact factor provide medium evidence.
- Low ranks, warning flags, no match, or invalid responses do not provide positive signal.
- Early warning fields add cautions and can reduce source confidence.
- The score is bounded from 0.0 to 1.0.

Existing ranking behavior changes:

- `venue_score` can be raised by verified EasyScholar evidence.
- `source_confidence` includes `easyscholar_score`.
- `ranking_rubric.dimensions.source_confidence.signals` includes `easyscholar_verified_metrics`.
- `ranking_protocol.reasons` includes concise EasyScholar evidence when present.
- `ranking_protocol.cautions` includes missing or failed EasyScholar verification only when it matters for interpretation.
- `ranking_rationale` says whether EasyScholar metrics were verified or unverified.

Tier rules:

- Tier A still requires stable identity, PDF, topic fit, and evidence beyond venue prestige.
- EasyScholar can help satisfy the venue or source quality signal.
- EasyScholar alone cannot pass a paper with weak topic fit, missing PDF, missing stable identity, or insufficient evidence.

## Failure Handling

The feature uses soft failure.

Soft-failure cases:

- `EASYSCHOLAR_SECRET_KEY` missing.
- EasyScholar API timeout.
- EasyScholar API non-200 response.
- EasyScholar response code not equal to success.
- No ranking data for the publication.
- Candidate has no publication name.
- Cache file is corrupt or expired.

Expected behavior:

- Discovery continues.
- Candidate remains eligible for existing EPI ranking.
- `easyscholar_score` is 0.0.
- Candidate and run artifacts record the failure status.
- User-facing reports mark EasyScholar metrics as `未核实` instead of guessing.

## Doctor And Reporting

`doctor` will add an `easyscholar` check:

- `ok` when `EASYSCHOLAR_SECRET_KEY` is set and a lightweight configuration check can run.
- `warning` when the key is missing.
- `warning` when runtime config is loaded but the env file is missing or unreadable.

`doctor` must not print the key.

`report.json` will include:

- EasyScholar enrichment summary.
- Count of matched, cache-hit, missing-key, no-match, api-error, timeout, invalid-response, and skipped candidates.
- Path to `easyscholar-record.json`.

`report.md` will include a concise quality-metrics section and mark unverified metrics as `未核实`.

## Tests

Unit tests:

- Parse successful EasyScholar raw response.
- Parse no-data and error responses.
- Score JCR, CAS, CCF, ABDC, AJG, IF, EI, CSSCI, PKU Core, CSCD, and warning fields.
- Normalize publication names and cache keys.
- Ensure secrets are never included in records or rendered reports.

Integration tests:

- `run_dry_run` default path calls EasyScholar enrichment before ranking.
- Missing key produces soft failure and still writes `rank.json`.
- API error produces soft failure and still writes `rank.json`.
- Cache hit avoids a client call and preserves parsed metrics.
- `--no-easyscholar` disables enrichment for the run.
- EasyScholar venue evidence changes ranking signals without overriding topic filters.

CLI and docs tests:

- Parser accepts `--no-easyscholar`.
- `doctor --json` includes EasyScholar set/missing status without the secret.
- `config-status --include-runtime --json` reports EasyScholar secret state without the secret.
- `plugins/epi/docs/attribution.md` credits `chaosman42/easyscholar-mcp`.
- Paper-discovery skill docs mention verified metrics, cache behavior, and `未核实`.

## Migration

Existing vaults need no manual migration.

If `quality_enrichment.easyscholar` is absent from `_epi\meta\epi-config.yaml`, EPI treats it as enabled with safe defaults. The config update path can later write explicit values if the user wants to tune timeout, TTL, or per-run candidate budget.

Existing `rank.json` files are not rewritten. Re-running `dry-run` creates new artifacts with EasyScholar fields.

## Open Decisions Resolved

- EasyScholar enrichment is default-on.
- EasyScholar failure is soft and does not block paper discovery.
- EPI ports the EasyScholar API logic to Python instead of nesting the upstream Node MCP server.
- EasyScholar metrics participate in ranking as bounded evidence signals.
- EasyScholar cannot by itself promote a weak or off-topic paper to Tier A.
