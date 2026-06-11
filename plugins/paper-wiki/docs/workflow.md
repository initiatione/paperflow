# Paper Wiki Workflow

Naming: Paper Wiki is this plugin's user-visible name. The current machine-facing plugin name is `paper-wiki`; `prw` is only a pre-Stage-2 legacy alias. Paper Source is the source-preparation sibling plugin; its current machine-facing plugin name is `paper-source`; `epi` is only a pre-Stage-2 legacy alias. PW/PS are conversational aliases only.

The plugin exposes one user-facing assistant for direct Paper Source paper deposition, read-only wiki Q&A, redo/deep extraction, wiki checks, wiki updates, and relink maintenance. `prw` is only a legacy alias for Paper Wiki.

Paper Wiki is a closed-loop paper wiki maintenance system. The fixed loop is:

```text
Check -> Diagnose -> Plan -> Act -> Verify -> Refresh -> Record -> Next
```

The ordinary path is: preflight Paper Source handoffs, diagnose wiki health, plan focused changes, deposit them into staged or formal pages under the target vault contract, verify provenance and language, refresh tracking/QMD surfaces, report record readiness to Paper Source `record-wiki-ingest`, and name the next action.

A Paper Wiki task is not complete until formal pages, tracking files, graph links, taxonomy, provenance, language gate, QMD freshness, and Paper Source record readiness have been checked or explicitly reported as skipped with reason.

The read-only ask path is:

```text
Question -> Scope -> Formal graph retrieval -> Evidence check -> Answer labels -> Correction candidates -> Stop
```

`ask_wiki` answers from the formal Obsidian graph first. It expands candidate pages through backlinks, outlinks, reciprocal links, aliases, tags, and co-links before falling back to frontmatter, manifest files, `index.md`, `hot.md`, and direct Markdown search. QMD is an optional accelerator, not the source of truth. This path uses no `log.md` write, does not write formal pages, does not refresh QMD, and does not write Paper Source artifacts. It reports correction candidates and uses ask before repair if the user wants the issues fixed.

Paper Wiki owns reading the paper wiki vault state, reading Paper Source handoff artifacts, writing or repairing formal wiki pages, fixing links/tags/aliases/duplicate concepts/orphan pages, updating `.manifest.json` or `manifest`, `index.md`, `log.md`, `hot.md`, refreshing `final-source-review.json`, and running post-task checks.

Paper Source owns paper discovery, ranking, download, MinerU parsing, paper wiki vault bootstrap through Paper Source `wiki-setup`, `paper-gate`, human approval, and `record-wiki-ingest`.

Paper Wiki assumes Paper Source `wiki-setup` has initialized the target vault contract. It checks the core `_paper_source` bootstrap (`_paper_source/`, `_paper_source/raw/`, `_paper_source/staging/`, `_paper_source/meta/`, `_paper_source/policies/`), legacy `_epi/` bootstrap, `_meta/`, `.obsidian`, `.git`, and the seven formal page roots; when missing core vault structure blocks work, Paper Wiki reports the capability gap and points back to Paper Source `wiki-setup`. Paper Wiki does not initialize, repair, silently create, or reset the vault, and it does not reset Paper Source state. Missing `_paper_source/runs/`, `_paper_source/cache/`, `_paper_source/tmp/`, `_paper_source/tmp-manual-pdfs/`, `_paper_source/quarantine/`, or `_paper_source/evolution/` is not a bootstrap failure because those Paper Source directories are created on demand.

Default checks are Quick + Targeted. Quick check reads manifest/index/log/hot, pending Paper Source handoffs, and recently changed pages. Targeted check scans only the current source, concept, tag, alias, page-family, and link neighborhood. Full check is reserved for explicit comprehensive audits or systemic link/tag chaos.

Redo requests such as `重做`, `重新提取`, `更详细提取`, or batch redo re-read the original Paper Source bundle, compare existing formal pages, and write direct updates or staged patches according to risk.

Update and relink requests repair the graph before they polish prose. Paper Wiki checks broken wikilinks, ambiguous aliases, duplicate concept owners, forbidden internal links, stale redirects, fragmented tags, and relationship direction mistakes, then applies conservative link repair under the target vault contract.

Frontmatter-only metadata repair is the lightweight path for non-semantic property fixes. When the user only asks to add a verified `github:` property for a code-bearing paper, normalize a property value, or expose an already-verified repository link without changing claims, formulas, figure/table evidence, evidence tier, relationships, aliases with semantic impact, lifecycle, or page body prose, edit only frontmatter and keep `sources:` as scan-friendly short source labels. Keep the full clickable PDF URI in the body `## 原文与证据入口`. Do not trigger graph-aware rewrite, dependent-page rewrite, `final-source-review.json`, `paper-wiki-record-request.json`, or Paper Source `record-wiki-ingest` readiness for this metadata-only path. Escalate to the full update/rewrite path only when the metadata changes semantic claims, evidence, relationships, lifecycle, body prose, or downstream synthesis.

QMD is QMD-compatible support, not the wiki source of truth. Paper Wiki may use QMD for retrieval and freshness checks, then run `qmd update` and `qmd embed` after write-heavy work. If QMD is unavailable, stale, slow, or noisy, Paper Wiki must fallback to manifest, `.manifest.json`, `index.md`, `log.md`, `hot.md`, and direct file search. It must not block on qmd query.

Paper Wiki health checks do not use a separate Paper Wiki CLI. Treat Paper Wiki as healthy only after plugin validation, source/cache manifest checks, `tests\paper_research_wiki\test_plugin_contract.py`, and the Paper Source bridge tests that protect `paper-research-wiki` handoff semantics pass. For runtime surface checks, confirm the QMD collection can see formal page roots and that `_paper_source/**`, legacy `_epi/**`, and formal-page snapshot internals remain absent from the indexed surface. If a Codex CLI marketplace command cannot see configured marketplaces in the current shell, report that as a CLI visibility caveat and verify cache/config/new-session skill loading separately.

Paper Source prepares source bundles and handoff artifacts. Paper Wiki/PW reads them and performs the formal wiki-side work without taking over Paper Source discovery, MinerU parsing, paper-gate, human approval, or record-only completion.

Completion reports must include pages created or updated, links/tags/aliases repaired, tracking files updated, QMD refreshed / skipped / failed with fallback, remaining risks, and the next Paper Source/Paper Wiki action.
