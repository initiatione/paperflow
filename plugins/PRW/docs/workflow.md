# Paper Research Wiki Workflow

The plugin exposes one user-facing assistant for direct EPI paper deposition, redo/deep extraction, wiki checks, wiki updates, and relink maintenance.

PRW is a closed-loop paper wiki maintenance system. The fixed loop is:

```text
Check -> Diagnose -> Plan -> Act -> Verify -> Refresh -> Record -> Next
```

The ordinary path is: preflight EPI handoffs, diagnose wiki health, plan focused changes, deposit them into staged or formal pages under the target vault contract, verify provenance and language, refresh tracking/QMD surfaces, report record readiness to EPI `record-wiki-ingest`, and name the next action.

A PRW task is not complete until formal pages, tracking files, graph links, taxonomy, provenance, language gate, QMD freshness, and EPI record readiness have been checked or explicitly reported as skipped with reason.

PRW owns reading the paper wiki vault state, reading EPI handoff artifacts, writing or repairing formal wiki pages, fixing links/tags/aliases/duplicate concepts/orphan pages, updating `.manifest.json` or `manifest`, `index.md`, `log.md`, `hot.md`, refreshing `final-source-review.json`, and running post-task checks.

EPI owns paper discovery, ranking, download, MinerU parsing, `paper-gate`, human approval, and `record-wiki-ingest`.

Default checks are Quick + Targeted. Quick check reads manifest/index/log/hot, pending EPI handoffs, and recently changed pages. Targeted check scans only the current source, concept, tag, alias, page-family, and link neighborhood. Full check is reserved for explicit comprehensive audits or systemic link/tag chaos.

Redo requests such as `重做`, `重新提取`, `更详细提取`, or batch redo re-read the original EPI source bundle, compare existing formal pages, and write direct updates or staged patches according to risk.

Update and relink requests repair the graph before they polish prose. PRW checks broken wikilinks, ambiguous aliases, duplicate concept owners, forbidden internal links, stale redirects, fragmented tags, and relationship direction mistakes, then applies conservative link repair under the target vault contract.

QMD is QMD-compatible support, not the wiki source of truth. PRW may use QMD for retrieval and freshness checks, then run `qmd update` and `qmd embed` after write-heavy work. If QMD is unavailable, stale, slow, or noisy, PRW must fallback to manifest, `.manifest.json`, `index.md`, `log.md`, `hot.md`, and direct file search. It must not block on qmd query.

EPI prepares source bundles and handoff artifacts. Paper Research Wiki reads them and performs the formal wiki-side work without taking over EPI discovery, MinerU parsing, paper-gate, human approval, or record-only completion.

Completion reports must include pages created or updated, links/tags/aliases repaired, tracking files updated, QMD refreshed / skipped / failed with fallback, remaining risks, and the next EPI/PRW action.
