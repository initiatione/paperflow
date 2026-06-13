# Paper Wiki Structure

This plugin lives at `plugins/paper-wiki`; its user-visible display name is Paper Wiki, and its current machine-facing plugin name is `paper-wiki`. `prw` is a pre-Stage-2 legacy alias.

Paper Wiki's source-preparation sibling is Paper Source, whose current machine-facing plugin name is `paper-source`; `epi` is a pre-Stage-2 legacy alias.

Paper Wiki has one public router skill: `skills/paper-research-wiki/SKILL.md`. PW/PS are conversational aliases only.

It also has one supporting language skill: `skills/paper-wiki-language/SKILL.md`. Formal page writing workflows read it before drafting or materially rewriting pages so Chinese prose quality is enforced alongside provenance.

Detailed behavior lives in workflows and references so users can invoke the plugin with natural requests instead of skill names. The structure follows a skill-based-architecture style: a short router, internal workflows, reusable references, and stable rules.

The router skill treats Paper Wiki as a closed-loop maintenance system, not a one-shot deposition tool. Workflow files internalize Ar9av/obsidian-wiki patterns into `Check -> Diagnose -> Plan -> Act -> Verify -> Refresh -> Record -> Next`, plus Quick + Targeted checks by default and Full check only for explicit comprehensive audits or systemic graph problems.

Governance is layered. `kepano/obsidian-skills` is the Obsidian syntax authority for properties/frontmatter, wikilinks, embeds, callouts, tags, Markdown links, math, bases, and canvas files. Paper Wiki is the paper-evidence and formal-graph layer: it owns source-grounded claims, formulas, figure/table evidence, relationships, page-family maintenance, content relationship repair, and record readiness. The target vault contract owns local taxonomy, page ownership, staged writes, and migration policy; sample vaults are references, not hard schemas.

Read-only wiki Q&A lives in `skills/paper-research-wiki/workflows/ask-wiki.md`. It retrieves from the formal Obsidian graph first, expands through backlinks, outlinks, aliases, tags, and co-links, and then uses QMD only as an optional accelerator with fallback to frontmatter, manifest files, `index.md`, `hot.md`, and direct Markdown search. It reports correction candidates but does not write `log.md`, formal pages, QMD, or Paper Source artifacts.

`rules/wiki-writing-standard-brief.md` is the always-read summary used for route matching and lightweight checks. `rules/wiki-writing-standard.md` is the mandatory full page-writing standard for formal paper wiki writes; load it before drafting, rewriting, materially repairing, relinking, or validating formal pages. It adapts Ar9av/obsidian-wiki page templates, merge-before-create behavior, provenance, wikilinks, relationships, tracking files, and lint/relink gates into the Paper Wiki paper workflow.

Paper Wiki assumes Paper Source `wiki-setup` has initialized the target vault. It checks bootstrap structure and reports missing vault structure as a capability gap, but bootstrap, repair, and reset remain Paper Source responsibilities.

Operational health is checked at three layers: source plugin validation, installed-cache plugin validation, and contract tests. Paper Wiki has no standalone CLI; its runtime correctness is protected by `paper-research-wiki` routing metadata, Paper Wiki contract tests, Paper Source handoff/record tests, and QMD surface checks that keep formal page roots visible while `_paper_source/**` and legacy `_epi/**` remain outside the indexed formal graph.
