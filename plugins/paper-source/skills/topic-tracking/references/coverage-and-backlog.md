# Topic Coverage And Backlog Reference

Use this reference when a user wants breadth, increments, or a reading plan for a research direction rather than a single paper.

## Incremental Delta

Build a delta table with these buckets:

- `net_new`: stable DOI/arXiv/title not seen in prior runs and not present in `_paper_source/raw`.
- `already_in_library`: candidate rejected by `already_in_library:<slug>` or matching `_paper_source/raw/*/metadata.json`.
- `seen_in_prior_run`: candidate appeared in an earlier `rank.json` or `report.json` but was not acquired.
- `changed_status`: known paper whose PDF, parse, critic, or wiki-ingest state changed.
- `uncertain_identity`: title-only or weak metadata match; ask for human review before suppressing.

If a future CLI has `--since <last-run|date>`, prefer it. Otherwise compare current artifacts with the last accepted run/date manually.

## Backlog Priority

Sort reading backlog by:

1. Hard identity and availability: DOI/arXiv/title match, PDF URL, open access.
2. Topic fit: current request and `_paper_source/meta/paper-source-config.yaml`, not broad recall terms alone.
3. Quality: `quality_tier`, `quality_gate`, venue/source confidence, verified metrics if present.
4. Incremental value: fills a missing method/task/benchmark/citation cluster.
5. Readiness: acquisition status, parse status, parse fidelity, critic state, handoff state.
6. Human value: likely to change the user's mental model or experiment plan.

Do not let old queue order dominate backlog priority.

## Coverage Axes

Report coverage across the axes that matter for the topic:

- Source and venue family.
- Year and recency.
- Paper type: empirical, theoretical, benchmark/dataset, method, system, survey/review.
- Method family and task/application setting.
- Dataset, benchmark, metric, and baseline.
- Backward references and forward cited-by clusters when review completeness matters.
- Known gaps from `recall_gap_checks`.

For systematic review mode, state whether backward/forward snowballing has been done. If not, say the coverage is search-only.

## Parse Fidelity Summary

After `prepare-ranked`, summarize whether the reader can be trusted:

- Markdown present and non-empty.
- Non-empty native TeX present, or Markdown-only parse requiring formula review from MinerU Markdown/PDF.
- Image/figure count and whether images were reviewed.
- Manifest present and complete.
- Parse warning/error text, including done-but-no-Markdown cases.
- Decision: `reader-ok`, `reader-with-pdf-check`, or `pdf-first`.

## Acquisition Fallback State

Failed `acquire-record.json` should be translated for the researcher:

- `no-url`: metadata exists but no downloadable PDF route.
- `access-denied`: source denied access; try arXiv/open-access/mirror.
- `not-found`: URL is dead; verify DOI/arXiv/source.
- `rate-limited` or `server-error`: retry later.
- `network`: retry or switch network/source.
- `empty-pdf`: retry or switch source.
- `already-exists`: use existing raw paper or explicit redo.

Do not describe an acquisition failure as "paper does not exist" unless identity verification also failed.
