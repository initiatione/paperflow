# Paper Research Wiki Structure

This plugin lives at `plugins/PRW` and has one public router skill: `skills/paper-research-wiki/SKILL.md`.

It also has one supporting language skill: `skills/paper-wiki-language/SKILL.md`. Formal page writing workflows read it before drafting or materially rewriting pages so Chinese prose quality is enforced alongside provenance.

Detailed behavior lives in workflows and references so users can invoke the plugin with natural requests instead of skill names. The structure follows a skill-based-architecture style: a short router, internal workflows, reusable references, and stable rules.

The router skill treats PRW as a closed-loop maintenance system, not a one-shot deposition tool. Workflow files internalize Ar9av/obsidian-wiki patterns into `Check -> Diagnose -> Plan -> Act -> Verify -> Refresh -> Record -> Next`, plus Quick + Targeted checks by default and Full check only for explicit comprehensive audits or systemic graph problems.

`rules/wiki-writing-standard.md` is the mandatory page-writing standard for formal paper wiki writes. It adapts Ar9av/obsidian-wiki page templates, merge-before-create behavior, provenance, wikilinks, relationships, tracking files, and lint/relink gates into the PRW paper workflow.

PRW assumes EPI `wiki-setup` has initialized the target vault. It checks bootstrap structure and reports missing vault structure, but bootstrap, repair, and reset remain EPI responsibilities.

Operational health is checked at three layers: source plugin validation, installed-cache plugin validation, and contract tests. PRW has no standalone CLI; its runtime correctness is protected by `paper-research-wiki` routing metadata, PRW contract tests, EPI handoff/record tests, and QMD surface checks that keep formal page roots visible while `_epi/**` remains outside the indexed formal graph.
