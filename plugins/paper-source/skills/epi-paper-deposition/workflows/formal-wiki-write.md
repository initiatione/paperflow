# Formal Wiki Write Compatibility Adapter

Use this workflow only when a legacy EPI deposition request names legacy `wiki_deposition_task.json` or `epi-wiki-deposition`.

## Load Inputs

1. Locate `_epi/staging/papers/<slug>/wiki-ingest-brief.json`.
2. If `wiki-ingest-brief.json` is missing and only `wiki_deposition_task.json` exists, stop and route back to EPI to regenerate or repair the brief.
3. Read the target vault `AGENTS.md` and `_meta/*` contract files when present.

## Route

Invoke PRW `$paper-research-wiki` for formal paper wiki work. PRW owns source-first deposition, graph-aware rewrite, provenance, language, link repair, QMD boundary reporting, `final-source-review.json`, and post-task checks.

This compatibility adapter does not duplicate PRW page-family, frontmatter, language, or lint rules. It only preserves compatibility with old EPI artifact names.

Internal `_epi/` pages must not enter the formal graph.
