# PRW Wiki Ask Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only PRW/EPI wiki question-answering path that answers natural research questions from the formal paper wiki graph, labels evidence versus inference, and reports correction candidates without writing by default.

**Architecture:** Extend the existing EPI `wiki_query.py` module with a new `ask_wiki` graph retrieval pipeline and renderer while preserving the existing manifest-filter `wiki-query` behavior. Expose the capability through a new `wiki-ask` CLI command, then route PRW natural question intents to a new thin workflow that treats QMD as an optional accelerator and correction findings as post-answer candidates.

**Tech Stack:** Python stdlib, pytest, Codex plugin skill/workflow metadata, Markdown/Obsidian wikilink parsing.

---

### Task 1: Behavior Tests

**Files:**
- Modify: `tests/epi/test_wiki_query.py`
- Modify: `tests/epi/test_cli_parser.py`
- Modify: `tests/paper_research_wiki/test_plugin_contract.py`

- [x] Add failing tests for `ask_wiki` graph retrieval: seed matching, outlinks, backlinks, co-linked pages, broken-link correction candidates, answer labels, and no `log.md` writes.
- [x] Add failing tests for `wiki-ask --question ... --json`.
- [x] Add failing PRW contract tests for the `ask_wiki` route and workflow wording.
- [x] Run focused tests and confirm they fail because the feature is missing.

### Task 2: EPI Query Core And CLI

**Files:**
- Modify: `plugins/epi/scripts/build/epi/wiki_query.py`
- Modify: `plugins/epi/scripts/build/epi/cli_parser.py`
- Modify: `plugins/epi/scripts/build/epi/cli.py`
- Modify: `plugins/epi/scripts/build/epi/cli_routes.py`

- [x] Implement formal-page discovery for `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/`.
- [x] Parse Markdown frontmatter aliases/tags plus Obsidian `[[wikilinks]]`.
- [x] Rank query seed pages and expand with outlinks, backlinks, reciprocal links, and co-linked pages.
- [x] Detect correction candidates for broken links, duplicate aliases, stale `index.md`/`hot.md` links, and formal pages linking `_epi/**` as graph pages.
- [x] Render labels: `【Wiki 证据】`, `【综合判断】`, `【推断】`, `【边界/不确定】`, plus `## 发现的 Wiki 问题 / 纠错候选`.
- [x] Add `wiki-ask` CLI with `--question`, `--limit`, `--max-hops`, and `--json`.

### Task 3: PRW/EPI Skill And Docs Contract

**Files:**
- Modify: `plugins/PRW/skills/routing.yaml`
- Modify: `plugins/PRW/skills/paper-research-wiki/SKILL.md`
- Create: `plugins/PRW/skills/paper-research-wiki/workflows/ask-wiki.md`
- Modify: `plugins/PRW/docs/workflow.md`
- Modify: `plugins/PRW/docs/structure.md`
- Modify: `plugins/PRW/docs/epi-integration.md`
- Modify: `plugins/epi/docs/workflow.md`
- Modify: `plugins/epi/docs/structure.md`
- Modify: `plugins/epi/.codex-plugin/plugin.json`
- Modify: `plugins/PRW/.codex-plugin/plugin.json`

- [x] Add a public PRW `ask_wiki` route and workflow.
- [x] Keep `SKILL.md` thin and route-heavy; workflow owns the detailed process.
- [x] Document that this route is read-only: no `log.md`, no formal-page edits, QMD optional, correction candidates ask-before-repair.
- [x] Bump EPI and PRW minor versions for new user-visible capability.

### Task 4: Verification

**Files:**
- No new implementation files unless tests expose a necessary split.

- [x] Run focused pytest for EPI query, CLI parser, and PRW contract.
- [x] Run plugin development gates from `docs/plugin-development.md`.
- [x] Run `compileall` on changed Python modules.
- [x] Run `git diff --check`.
- [x] Review changed files for source-vs-runtime boundary, no vault hardcoded path, no writes in ask flow.
