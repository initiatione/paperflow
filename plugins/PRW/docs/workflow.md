# Paper Research Wiki Workflow

The plugin exposes one user-facing assistant for direct EPI paper deposition, read-only wiki Q&A, redo/deep extraction, wiki checks, wiki updates, and relink maintenance.

PRW is a closed-loop paper wiki maintenance system. The fixed loop is:

```text
Check -> Diagnose -> Plan -> Act -> Verify -> Refresh -> Record -> Next
```

The ordinary path is: preflight EPI handoffs, diagnose wiki health, plan focused changes, deposit them into staged or formal pages under the target vault contract, verify provenance and language, refresh tracking/QMD surfaces, report record readiness to EPI `record-wiki-ingest`, and name the next action.

A PRW task is not complete until formal pages, tracking files, graph links, taxonomy, provenance, language gate, QMD freshness, and EPI record readiness have been checked or explicitly reported as skipped with reason.

The read-only ask path is:

```text
Question -> Scope -> Formal graph retrieval -> Evidence check -> Answer labels -> Correction candidates -> Stop
```

`ask_wiki` answers from the formal Obsidian graph first. It expands candidate pages through backlinks, outlinks, reciprocal links, aliases, tags, and co-links before falling back to frontmatter, manifest files, `index.md`, `hot.md`, and direct Markdown search. QMD is an optional accelerator, not the source of truth. This path uses no `log.md` write, does not write formal pages, does not refresh QMD, and does not write EPI artifacts. It reports correction candidates and uses ask before repair if the user wants the issues fixed.

PRW owns reading the paper wiki vault state, reading EPI handoff artifacts, writing or repairing formal wiki pages, fixing links/tags/aliases/duplicate concepts/orphan pages, updating `.manifest.json` or `manifest`, `index.md`, `log.md`, `hot.md`, refreshing `final-source-review.json`, and running post-task checks.

EPI owns paper discovery, ranking, download, MinerU parsing, paper wiki vault bootstrap through EPI `wiki-setup`, `paper-gate`, human approval, and `record-wiki-ingest`.

PRW assumes EPI `wiki-setup` has initialized the target vault contract. It checks the core `_epi` bootstrap (`_epi/`, `_epi/raw/`, `_epi/staging/`, `_epi/meta/`, `_epi/policies/`), `_meta/`, `.obsidian`, `.git`, and the seven formal page roots; when missing core vault structure blocks work, PRW reports the gap and points back to EPI `wiki-setup`. PRW does not initialize, repair, silently create, or reset the vault, and it does not reset EPI state. Missing `_epi/runs/`, `_epi/cache/`, `_epi/tmp/`, `_epi/tmp-manual-pdfs/`, `_epi/quarantine/`, or `_epi/evolution/` is not a bootstrap failure because those EPI directories are created on demand.

Default checks are Quick + Targeted. Quick check reads manifest/index/log/hot, pending EPI handoffs, and recently changed pages. Targeted check scans only the current source, concept, tag, alias, page-family, and link neighborhood. Full check is reserved for explicit comprehensive audits or systemic link/tag chaos.

Redo requests such as `重做`, `重新提取`, `更详细提取`, or batch redo re-read the original EPI source bundle, compare existing formal pages, and write direct updates or staged patches according to risk.

Update and relink requests repair the graph before they polish prose. PRW checks broken wikilinks, ambiguous aliases, duplicate concept owners, forbidden internal links, stale redirects, fragmented tags, and relationship direction mistakes, then applies conservative link repair under the target vault contract.

QMD is QMD-compatible support, not the wiki source of truth. PRW may use QMD for retrieval and freshness checks, then run `qmd update` and `qmd embed` after write-heavy work. If QMD is unavailable, stale, slow, or noisy, PRW must fallback to manifest, `.manifest.json`, `index.md`, `log.md`, `hot.md`, and direct file search. It must not block on qmd query.

PRW health checks do not use a separate PRW CLI. Treat PRW as healthy only after plugin validation, source/cache manifest checks, `tests\paper_research_wiki\test_plugin_contract.py`, and the EPI bridge tests that protect `paper-research-wiki` handoff semantics pass. For runtime surface checks, confirm the QMD collection can see formal page roots and that `_epi/**` and formal-page snapshot internals remain absent from the indexed surface. If a Codex CLI marketplace command cannot see configured marketplaces in the current shell, report that as a CLI visibility caveat and verify cache/config/new-session skill loading separately.

EPI prepares source bundles and handoff artifacts. Paper Research Wiki reads them and performs the formal wiki-side work without taking over EPI discovery, MinerU parsing, paper-gate, human approval, or record-only completion.

Completion reports must include pages created or updated, links/tags/aliases repaired, tracking files updated, QMD refreshed / skipped / failed with fallback, remaining risks, and the next EPI/PRW action.
