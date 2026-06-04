# Paper Research Wiki Structure

This plugin lives at `plugins/PRW` and has one public router skill: `skills/paper-research-wiki/SKILL.md`.

It also has one supporting language skill: `skills/paper-wiki-language/SKILL.md`. Formal page writing workflows read it before drafting or materially rewriting pages so Chinese prose quality is enforced alongside provenance.

Detailed behavior lives in workflows and references so users can invoke the plugin with natural requests instead of skill names. The structure follows a skill-based-architecture style: a short router, internal workflows, reusable references, and stable rules.

`rules/wiki-writing-standard.md` is the mandatory page-writing standard for formal paper wiki writes. It adapts Ar9av/obsidian-wiki page templates, merge-before-create behavior, provenance, wikilinks, relationships, tracking files, and lint/relink gates into the PRW paper workflow.
