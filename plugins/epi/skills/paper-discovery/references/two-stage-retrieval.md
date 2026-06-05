# Two-Stage Retrieval

Use two-stage retrieval when the user cares about high quality, latest work, or non-review precision. The goal is to avoid trusting the first 10 returned records from one source.

## Stage 1: High Recall Candidate Pool

Run multiple query variants across routed sources:

- 5-8 query variants from `query-planner.md`.
- T1 sources first: `arxiv`, `semantic`, `openalex`, CrossRef-style metadata when available.
- T2 verification sources: publisher/venue pages, IEEE/ACM/Springer/ScienceDirect, official proceedings.
- T3 recall hints only when needed: Google Scholar, lab/project pages, configured field-curated lists, community discussion.

Suggested pool size:

- Small interactive search: 30-60 raw candidates.
- High-quality/latest search: 80-150 raw candidates if source limits allow.
- User asks for 10 papers: still build a larger pool, then rank down to kept papers.

EPI `dry-run` now performs this by default: it writes `query-plan.json`, searches each query variant, stores per-variant evidence in `search-record.json.query_records`, and then sends the merged raw candidate pool through normalization, filtering, and ranking. Discovery excludes review/survey/meta candidates by default; keep reviews only when the user explicitly asks for review or survey papers. Use `--no-query-plan` only when debugging one raw search query.

## Stage 2: Precision Filtering And Ranking

Filter and rank after the pool exists:

1. Deduplicate by DOI, arXiv ID, stable URL, normalized title, and title+first-author+year.
2. Deduplicate against `_epi/raw/*/metadata.json`.
3. Remove hard exclusions such as review/survey when requested.
4. Enforce `domain_focus_terms` when present. This is the hard anchor gate for the current request; broad config or method terms should not let method-only papers pass.
5. Classify paper type from title/abstract using `paper-type-taxonomy.md`.
6. Verify identity: title, year, venue, DOI/arXiv ID, PDF.
7. Score topic fit by concept block coverage.
8. Score quality by evidence: venue prior, citation count, field-specific validation, replication, benchmark, code/data, or other quality signals from config/query plan.
9. Emit `ranking_rubric` and mark metrics not verified in the current run as `未核实`.

## Scoring Shape

Do not publish a single fake precision number to the user, but reason with this structure:

```text
reading_priority =
  topic_fit
  + method_fit
  + validation_strength
  + venue_prior
  + citation_signal
  + recency
  + pdf_code_availability
  - review_or_survey_penalty
  - method_only_without_domain_anchor_penalty
  - weak_identity_penalty
  - already_in_library_penalty
```

Stage 1 should be generous. Stage 2 should be strict.
