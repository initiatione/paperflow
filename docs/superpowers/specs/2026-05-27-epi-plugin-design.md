# EPI Plugin Design

Date: 2026-05-27
Status: design-review
Owner: initiatione
Repository: `D:\paper-search`

## Purpose

Build a Codex marketplace-installable plugin for engineering literature intelligence. The plugin should search for high-quality papers in user-defined domains, first targeting robotics, AI, embodied intelligence, and control; collect and preserve raw paper assets; parse PDFs through MinerU; produce agent-readable reader outputs; critic-check the outputs; and promote only verified knowledge into a dedicated LLM Wiki vault.

This is not a single skill and not a local script bundle. It is a plugin that packages skills, MCP wiring, scripts, templates, and documentation into an installable workflow.

## Confirmed Decisions

- Plugin identifier and folder name target: `epi`.
- Marketplace display name target: `EPI`.
- Expanded workflow name: Engineering Paper Intelligence.
- Search layer wraps mature infrastructure, primarily `openags/paper-search-mcp`, instead of rebuilding every source adapter from scratch.
- The existing `mineru-paper-parser` capability becomes one stage inside the larger plugin.
- A new paper-specific wiki vault must be created at `D:\paper-research-wiki`.
- The plugin must not write paper workflow data into the existing `D:\Obsidian-wiki`.
- The paper wiki follows the Ar9av/LLM Wiki pattern: raw source -> compiled wiki -> schema.
- Raw PDF, MinerU Markdown, LaTeX, images, metadata, reader output, critic output, and run records must be retained.
- The full pipeline is automated through a state machine. The agent reads `run-state.json` and routes to MCP, scripts, or skills based on missing artifacts and current state.
- MVP orchestration is single-agent: one Codex agent runs the state machine and calls stage tools. Multi-agent reviewers, parallel critics, and specialized reader agents are explicitly post-MVP.
- The state machine may skip or reorder stages when that better satisfies the user's goal, but every deviation must be recorded.
- The critic layer is a hard quality gate before compiled wiki writes.
- Hard rule: no critic pass, no compiled wiki write.
- The workflow supports `dry-run`, budget controls, human gates, rollback, redo, and recritic.
- Self-evolution is skill-aware, evidence-backed, staged, and reversible.
- `skill-aware-evolve` never edits plugin code directly. It first proposes changes to controlled assets.
- The official Plugin Eval plugin is part of the EPI development and release workflow.
- Plugin Eval is not part of the paper runtime chain and does not replace `paper-quality-critic`, `parse-quality-critic`, or `reader-quality-critic`.
- Plugin Eval findings feed the `feedback -> skill-aware-evolve` loop as development-quality evidence.
- The first custom Plugin Eval metric pack for EPI must check the presence of `run-state.json`, the existence of a critic gate, the hard rule that no critic pass means no compiled wiki write, and retention of raw PDF plus metadata.

## Product Boundary

The plugin owns workflow intelligence and orchestration:

- User intent parsing and domain profile selection.
- Calling/wrapping the paper-search MCP.
- Candidate normalization, filtering, and ranking.
- PDF acquisition and provenance capture.
- MinerU parsing orchestration.
- Paper reader generation.
- Critic review.
- Staging and promotion into the dedicated paper wiki.
- Optional Zotero sync.
- Run reporting and feedback capture.
- Skill-aware evolution of profiles, checklists, templates, and routing rules.

The MVP orchestrator is not a general autonomous agent platform. It is a single-agent workflow runner that packages a staged literature pipeline into an installable Codex plugin.

The plugin does not own:

- The user's Zotero database.
- The user's existing general-purpose `D:\Obsidian-wiki`.
- Raw paper truth beyond preserving source artifacts.
- Automatic modification of plugin source code during normal operation.

## Plugin Structure

Target plugin layout:

```text
plugins/epi/
  .codex-plugin/
    plugin.json
  .mcp.json
  skills/
    paper-discover/
    paper-normalize/
    paper-filter/
    paper-ranker/
    paper-acquire/
    mineru-paper-parser/
    paper-reader/
    paper-critic/
    obsidian-llm-wiki/
    zotero-sync/
    paper-report/
    skill-aware-evolve/
  scripts/
    orchestrator.py
    paper_search_adapter.py
    normalize_candidates.py
    filter_candidates.py
    rank_papers.py
    acquire_papers.py
    run_mineru_parse.py
    run_reader.py
    run_critic.py
    promote_to_wiki.py
    zotero_sync.py
    report_run.py
    evolve_assets.py
  templates/
    interests.example.yaml
    ranking.example.yaml
    filter-rules.example.yaml
    critic-checklist.example.yaml
    reader-template.md
    wiki-reference-template.md
    promotion-record.schema.json
  docs/
    workflow.md
    config.md
    recovery.md
    attribution.md
    evaluation.md
  metric-packs/
    epi-quality-gates/
      manifest.json
      emit-epi-quality-gates.js
  vendor-notices/
```

The plugin directory contains distributable logic and templates only. Runtime paper data lives in the configured paper wiki and run directories.

## Mature MCP Wrapping Strategy

The plugin should wrap `openags/paper-search-mcp` as a pinned, attributed dependency rather than copying its source into the plugin by default.

Required behavior:

- Pin the compatible upstream version or commit in plugin docs/config.
- Provide an install/probe path that verifies the MCP is available before discovery.
- Start or invoke the MCP through a plugin-owned wrapper so downstream scripts see a stable adapter contract.
- Normalize upstream tool responses into this plugin's `search-record.json` and `normalized.json` schemas.
- Record upstream version, command, query, endpoint, and source names in every discovery run.
- Fail closed when the MCP is unavailable: report the missing dependency and stop before fabricating search results.
- Keep a future `vendor` mode possible, but require license attribution and an explicit sync policy before vendoring upstream code.

The wrapper boundary prevents the rest of the pipeline from depending on upstream response quirks. Only `paper_search_adapter.py` should know the exact `paper-search-mcp` invocation details.

## Dedicated Paper Wiki

Default vault:

```text
D:\paper-research-wiki
```

Required layout:

```text
D:\paper-research-wiki\
  _raw\
    papers\
  _staging\
    papers\
  _quarantine\
    papers\
  _runs\
  _evolution\
    proposals\
    active\
    archive\
  _meta\
  references\
  concepts\
  synthesis\
  entities\
  skills\
  projects\
  journal\
  index.md
  log.md
  hot.md
  .manifest.json
  .obsidian\
```

The vault schema must state that `_raw`, `_staging`, `_quarantine`, `_runs`, and `_evolution` are operational layers rather than compiled knowledge pages.

## Per-Paper Artifact Layout

Each paper receives a stable slug. Raw and generated assets live under:

```text
D:\paper-research-wiki\_raw\papers\<paper-slug>\
  paper.pdf
  search-record.json
  normalized.json
  filter-report.json
  rank.json
  metadata.json
  acquire-record.json
  run-manifest.json
  mineru\
    paper.md
    paper.tex
    images\
  reader\
    reader.md
    figures.md
    reproducibility.md
    implementation-ideas.md
  critic\
    paper-quality-critic.md
    parse-quality-critic.md
    reader-quality-critic.md
    critic-report.json
  wiki-record.json
  zotero-record.json
```

Staging drafts live under:

```text
D:\paper-research-wiki\_staging\papers\<paper-slug>\
  references\
    <paper-slug>.md
  concepts\
  synthesis\
  promotion-plan.json
```

Failed or suspicious outputs move to:

```text
D:\paper-research-wiki\_quarantine\papers\<paper-slug>\
```

Compiled knowledge is promoted only to:

```text
D:\paper-research-wiki\references\<paper-slug>.md
D:\paper-research-wiki\concepts\<method-or-topic>.md
D:\paper-research-wiki\synthesis\<cross-paper-topic>.md
```

## Pipeline

The confirmed end-to-end chain is:

```text
configure -> discover -> normalize -> filter -> rank -> acquire -> parse -> read -> critic -> staging -> promote-to-wiki -> zotero -> report -> feedback -> skill-aware-evolve
```

### configure

Loads and validates user configuration:

- Research domains.
- Interest profiles.
- Venue weights.
- Filter rules.
- Ranking weights.
- Critic checklist.
- Budget limits.
- Human gate policy.
- Vault paths.
- MinerU token path.
- Zotero enablement.

Initial target profile:

```text
robotics / AI / embodied intelligence / control
```

### discover

Calls mature search infrastructure, especially `openags/paper-search-mcp`, to search multiple sources. The plugin should preserve raw source responses and endpoint/query provenance.

Preferred sources for the initial profile:

- arXiv
- Semantic Scholar
- OpenAlex
- Crossref
- dblp
- Unpaywall
- CORE or other PDF-supporting sources when useful

### normalize

Standardizes multi-source results and deduplicates candidates. It produces `normalized.json`.

Responsibilities:

- Merge results by DOI, arXiv ID, title similarity, and canonical URL.
- Normalize title, authors, year, venue, abstract, DOI, arXiv ID, PDF URL, code URL, citation count, source list, and raw provenance.
- Mark duplicates and source disagreements.
- Preserve all source records for audit.

### filter

Performs initial exclusion. It produces `filter-report.json`.

Default exclusion classes:

- Outside target domain.
- No accessible PDF, unless user explicitly allows metadata-only tracking.
- Duplicate of already accepted paper.
- Already present in the paper wiki or Zotero.
- Clearly low-quality or irrelevant source.
- Missing enough metadata to rank.

Filter is allowed to be conservative. Borderline candidates can be retained for ranking with a warning instead of being dropped.

### rank

Scores remaining papers for quality and relevance. It produces `rank.json`.

Ranking signals:

- Topic relevance to the active interest profile.
- Venue or journal tier.
- Citation count and citation velocity when available.
- Publication year and freshness.
- PDF availability.
- Code, project page, dataset, benchmark, or reproducibility signals.
- Author, lab, or institution signals when configured.
- User boost/block keywords.
- Prior user feedback.

Impact factor is not sufficient for robotics, AI, and control. Conference and community venue tiers must be first-class signals.

### acquire

Downloads or links the paper PDF and saves metadata. It produces `paper.pdf`, `metadata.json`, and `acquire-record.json`.

Requirements:

- Record the PDF source URL and retrieval timestamp.
- Verify file presence and size.
- Avoid overwriting existing raw PDFs unless explicitly rerunning acquisition.
- Prefer open/legal sources.

### parse

Calls MinerU API to parse the PDF. It produces Markdown, LaTeX, images, and parse metadata.

Requirements:

- Use the existing MinerU precise batch API workflow.
- Produce one paper directory with `paper.md`, `paper.tex`, and `images/`.
- Verify image links.
- Record parse job ID, timestamps, and failures.

### read

Generates agent-readable paper analysis. It produces the reader files.

Reader outputs:

- `reader.md`: Chinese-first source-grounded paper reading.
- `figures.md`: figure/table-aware explanation.
- `reproducibility.md`: code/data/experiment/reproduction assessment.
- `implementation-ideas.md`: possible transfer ideas for the user's projects.

Reader should borrow the spirit of figure-aware and source-grounded reading from Nature-style paper reader workflows, while staying adapted to engineering papers.

Reader claims must be evidence-addressable. Important claims in `reader.md`, `figures.md`, and `reproducibility.md` should cite at least one of:

- MinerU Markdown section or heading.
- Figure/table identifier and image path.
- PDF page number when available.
- Metadata field and source.
- Explicitly marked inference.

Unsupported guesses must be marked as inferred or moved into `implementation-ideas.md`. They must not be promoted as paper facts.

### critic

Runs quality gates before formal wiki write. It produces critic reports.

Sub-critics:

- `paper-quality-critic`: checks paper quality and collection worthiness.
- `parse-quality-critic`: checks PDF parsing completeness, missing images, broken formulas, and layout issues.
- `reader-quality-critic`: checks summary fidelity, hallucination risk, missed contributions, overstated claims, and unsupported inferences.

The critic must sample claim-level evidence, not just judge writing quality. It should verify that core claims in the reader can be traced back to raw artifacts or parser output. If a reader claim cannot be traced, the critic should choose `revise-reader`, `human-review`, or `quarantine` instead of `pass`.

Possible outcomes:

- `pass`
- `revise-reader`
- `redo-parse`
- `reject-paper`
- `quarantine`
- `human-review`

Hard rule:

```text
No critic pass, no compiled wiki write.
```

### staging

Creates wiki drafts under `_staging`. Staging allows review and rollback before compiled wiki changes.

Staging must include:

- Draft reference page.
- Proposed concept page updates.
- Proposed synthesis page updates.
- `promotion-plan.json`.

### promote-to-wiki

Promotes staged drafts into compiled wiki only after critic approval and any configured human gate.

Promotion must:

- Backup previous versions.
- Write `promotion-record.json`.
- Update `.manifest.json`.
- Append to `log.md`.
- Refresh `index.md` and `hot.md` if the wiki tooling supports it.
- Preserve provenance in frontmatter.
- Mark inferred or ambiguous content.

Promotion is transactional at the page-set level. Before writing compiled pages, the plugin must snapshot every page it may overwrite plus the relevant manifest/index/log state needed for rollback. If any write fails, the promotion should either complete recovery automatically or leave the run in a `promotion_failed` state with enough records to roll back.

`promotion-record.json` must include:

- Run ID and paper slug.
- Input artifact hashes.
- Staged draft paths.
- Promoted page paths.
- Previous page snapshot paths.
- Manifest/index/log update summary.
- Critic report references.
- Human gate decision, if any.
- Rollback command or script arguments.

### zotero

Optional Zotero synchronization.

Allowed outputs:

- Imported PDF.
- Imported BibTeX or RIS metadata.
- Tags and collection assignment.
- `zotero-record.json`.

The plugin must treat Zotero writes as explicit configured actions. If disabled, Zotero stage is skipped.

### report

Produces a human-readable and machine-readable run report:

- Accepted papers.
- Rejected papers and reasons.
- Quarantined papers.
- Critic failures.
- Budget usage.
- Wiki pages written.
- Zotero sync results.
- Next suggested actions.

### feedback

Captures user feedback:

- Accepted recommendations.
- Rejected recommendations.
- Papers the user manually promotes or demotes.
- Reader quality corrections.
- Wiki correction requests.
- Plugin Eval reports, benchmark results, and improvement briefs from EPI development.

Feedback updates run records and may generate evolution proposals.

### Plugin Eval Development Quality Layer

Plugin Eval is a development, release, and self-improvement quality layer for EPI itself. It evaluates the plugin and skills as software artifacts; it does not judge whether a paper is scientifically good, whether MinerU parsed a PDF correctly, or whether a reader summary is faithful.

Local confirmed Plugin Eval root:

```text
C:\Users\liuchf\.codex\plugins\cache\openai-curated\plugin-eval
```

Current local versioned path observed during design work:

```text
C:\Users\liuchf\.codex\plugins\cache\openai-curated\plugin-eval\603a6e80
```

Available Plugin Eval capabilities:

- `evaluate-plugin`
- `evaluate-skill`
- `improve-skill`
- `metric-pack-designer`
- `plugin-eval` CLI

Development loop:

```text
develop or modify EPI
  -> Plugin Eval analyze
  -> EPI custom metric pack
  -> benchmark typical tasks
  -> compare before/after
  -> generate improvement brief
  -> skill-aware-evolve proposal
  -> human review and validation
  -> activate approved asset changes
```

Known baseline from the existing `mineru-paper-parser` plugin:

```text
node C:\Users\liuchf\.codex\.tmp\plugins\plugins\plugin-eval\scripts\plugin-eval.js analyze D:\paper-search\plugins\mineru-paper-parser --format markdown
```

Observed result:

- Score: 40/100
- Grade: F
- Risk: high
- Main issues: missing `websiteURL`, `privacyPolicyURL`, and `termsOfServiceURL` in `plugin.json`; skill trigger description not explicit enough; Python script complexity is high; tests are missing.

EPI-specific metric pack initial checks:

- `run-state.json` exists for workflow runs that claim to be routed or completed.
- A critic gate is represented in routing, state, docs, and tests before compiled wiki promotion exists.
- The invariant `No critic pass, no compiled wiki write` is explicitly encoded and testable.
- Raw PDF and metadata retention is required by artifact contracts.

Metric-pack results are advisory development evidence. They may block a release if the user configures that policy, but they must not be used as a substitute for paper runtime critics.

### skill-aware-evolve

Analyzes evidence from runs and proposes improvements to controlled assets.

It may propose changes to:

- Search profiles.
- Filter rules.
- Ranking weights.
- Critic checklists.
- Reader templates.
- Wiki promotion rules.
- Routing rules.
- Common failure memory.
- Plugin and skill development rules derived from Plugin Eval reports, benchmarks, and custom metric packs.

It must not directly edit plugin code.

Evolution principle:

```text
Self-evolution must be skill-aware, evidence-backed, staged, and reversible.
```

Reflection types:

- `DISCOVERY`: a new rule or knowledge item is missing.
- `OPTIMIZATION`: an existing rule can be improved.
- `SKILL_DEFECT`: a rule or template is wrong.
- `EXECUTION_LAPSE`: the rule is valid but was not followed.

Proposal flow:

```text
D:\paper-research-wiki\_evolution\proposals\
  -> validated and approved
D:\paper-research-wiki\_evolution\active\
  -> superseded or rolled back
D:\paper-research-wiki\_evolution\archive\
```

Every activated evolution must have:

- Evidence links.
- A reversible diff or replacement record.
- Validation criteria.
- Activation timestamp.
- Rollback instructions.

## State Machine

The orchestrator owns `run-state.json` under `_runs/<run-id>/`.

MVP orchestration is single-agent. A Codex agent reads the state, selects the next stage, calls the relevant MCP/script/skill, records the result, and repeats. The design must preserve stage boundaries so later versions can replace selected stages with multi-agent reviewers, parallel critics, or specialized readers without changing the paper artifact contract.

Example states:

- `configured`
- `discovered`
- `normalized`
- `filtered`
- `ranked`
- `acquired`
- `parsed`
- `read`
- `critic_passed`
- `critic_failed`
- `staged`
- `promoted`
- `zotero_synced`
- `reported`
- `feedback_recorded`
- `evolution_proposed`
- `quarantined`
- `rolled_back`

Routing rules:

```text
missing search-record.json -> discover
missing normalized.json -> normalize
filter status rejected -> stop candidate
rank below threshold -> reject or hold
missing paper.pdf -> acquire
missing mineru/paper.md -> parse
missing reader/reader.md -> read
missing critic-report.json -> critic
critic failed -> redo, human review, or quarantine
critic passed and missing staging -> staging
staging approved and no compiled write -> promote-to-wiki
zotero enabled and not synced -> zotero
all stages complete -> report
feedback present -> feedback
evidence suggests rule change -> skill-aware-evolve
```

The state machine may choose a non-linear route when it better satisfies user intent. Examples:

- Run `normalize` again after discovering duplicate metadata.
- Re-run `parse` after parse critic detects missing images.
- Re-run `read` after reader critic detects unsupported claims.
- Skip Zotero when disabled.
- Stop after `rank` in dry-run mode.

Every route deviation must be logged.

### State Safety

The orchestrator must be idempotent and crash-recoverable.

Required safeguards:

- Use per-run and per-paper locks before writing artifacts.
- Treat each stage as a pure transition from declared inputs to declared outputs where possible.
- Record input file hashes, output file hashes, stage start/end timestamps, tool versions, and exit status.
- Never overwrite raw PDFs or source JSON unless the user explicitly runs a redo mode.
- Write stage outputs to a temporary path and then atomically move them into place.
- On restart, read `run-state.json` and artifact presence before deciding the next route.
- Mark partial failures explicitly, such as `parse_failed`, `reader_failed`, `critic_failed`, or `promotion_failed`.
- Prefer reusing verified artifacts over recomputing them when input hashes match.

These rules are what make full automation safe enough for unattended runs.

## Controls

### dry-run

Dry-run produces candidates, filtering, ranking, and planned actions without downloading PDFs, parsing, writing wiki pages, or writing Zotero.

### budget

Budgets can limit:

- Search results per source.
- Papers acquired.
- Papers parsed.
- Reader calls.
- Critic calls.
- MinerU API usage.
- Time per run.

### human gate

Configurable gates:

- Before PDF acquisition.
- Before MinerU parsing.
- Before formal wiki promotion.
- Before Zotero writes.
- Before activating evolution proposals.

Default first-version recommendation:

```text
auto through critic and staging;
manual gate before promote-to-wiki;
manual gate before Zotero writes;
manual gate before activating evolution proposals.
```

### rollback and redo

Required commands or script modes:

- `rollback paper <slug>`
- `redo acquire <slug>`
- `redo parse <slug>`
- `redo read <slug>`
- `recritic <slug>`
- `repromote <slug>`

Rollback must use `promotion-record.json` and backups rather than guessing.

Rollback scope must be explicit:

- Restore overwritten compiled wiki pages from snapshots.
- Remove newly created compiled pages listed in `promotion-record.json`.
- Restore or compensate `.manifest.json` changes.
- Append a rollback entry to `log.md` instead of deleting history.
- Mark the run and paper as `rolled_back`.
- Leave `_raw` artifacts intact unless the user explicitly deletes them.

## Wiki Page Rules

Reference pages should be concise compiled knowledge pages, not full reader dumps.

Each promoted paper page should include:

- Title.
- Canonical identifiers.
- Summary.
- Why it matters for the active domain.
- Method core.
- Evidence and experiments.
- Limitations.
- Reproduction signals.
- Links to related concepts and synthesis pages.
- Sources pointing to raw artifacts.
- Critic status.

Raw files and reader files stay under `_raw`. Main wiki pages refer to raw paths in frontmatter provenance rather than creating noisy graph edges to every artifact.

## Config

Core environment/config keys:

- `PAPER_SEARCH_HOME`
- `PAPER_WIKI_VAULT_PATH`
- `MINERU_TOKEN` or `.env/mineru.env`
- `PAPER_SEARCH_MCP_MODE`
- `PAPER_SEARCH_MCP_VERSION`
- `ZOTERO_ENABLED`
- `ZOTERO_COLLECTION`
- `HUMAN_GATE_MODE`
- `PAPER_PIPELINE_BUDGET`

User-editable config files:

- `interests.yaml`
- `venues.yaml`
- `ranking.yaml`
- `filter-rules.yaml`
- `critic-checklist.yaml`
- `routing-rules.yaml`
- `reader-template.md`
- `wiki-promotion-rules.yaml`

## First-Version Scope

Implementation should be split so the first useful version is small and testable.

### Phase 0: Foundation

- Rename or scaffold the target plugin shape for `epi`.
- Preserve the existing MinerU parser capability as an internal stage.
- Add config templates for interests, ranking, filters, critic, routing, and paper wiki paths.
- Add paper wiki initialization templates for `D:\paper-research-wiki`.
- Add attribution docs for wrapped dependencies.
- Add Plugin Eval documentation and an EPI-specific metric pack skeleton.

### Phase 1: Discovery Dry Run

- Implement MCP probe/wrapper for `openags/paper-search-mcp`.
- Implement `configure -> discover -> normalize -> filter -> rank`.
- Produce `search-record.json`, `normalized.json`, `filter-report.json`, and `rank.json`.
- Support dry-run and budget controls.
- Produce a run report without downloading, parsing, or writing the wiki.
- Run Plugin Eval with the EPI metric pack during development validation.

### Phase 2: One-Paper Ingest

- Acquire one selected paper.
- Parse it with MinerU.
- Generate reader outputs with claim-level evidence requirements.
- Run the three critic layers.
- Write staged wiki drafts only after critic pass.
- Keep manual gate before compiled wiki promotion.

### Phase 3: Safe Promotion

- Implement transactional `promote-to-wiki`.
- Update `.manifest.json`, `index.md`, `hot.md`, and `log.md`.
- Implement rollback, redo, and recritic for promoted papers.
- Validate that no compiled wiki write happens without critic pass.

### Phase 4: Optional Integrations

- Zotero sync.
- Automatic recurring digest.
- Full feedback learning.
- Active evolution application.
- Broader source adapters beyond the wrapped MCP.

### Phase 5: Multi-Agent Expansion

- Multi-agent reviewers for independent quality judgments.
- Parallel critics for paper, parse, reader, and wiki-promotion review.
- Specialized reader agents for methods, figures, reproducibility, and implementation transfer.
- Consensus or disagreement reports that feed back into critic and staging decisions.

Phase 5 must preserve the same artifact contracts and critic gate. It expands who performs the work, not where trusted knowledge is allowed to land.

## Risks and Mitigations

- Search dependency drift: pin the mature MCP version and record attribution.
- Dirty wiki risk: require critic pass and staging before compiled writes.
- Hallucinated summaries: reader output must be source-grounded and critic-checked.
- Parse corruption: parse critic checks pages, image links, formulas, and layout clues.
- API cost creep: dry-run and budget controls are first-class.
- Rule drift: skill-aware evolution is staged and reversible.
- Overgrown plugin scope: keep search, ranking, parsing, reading, critic, wiki, Zotero, and evolution as separate skills/scripts with explicit contracts.
- Agent-platform scope creep: MVP stays single-agent and defers multi-agent reviewers, parallel critics, and specialized readers to Phase 5.
- Evaluation-role confusion: keep Plugin Eval as a plugin-development quality layer and keep runtime paper critics as the only gate for paper/wiki truth.

## Open Implementation Questions

- Exact command and environment mechanism for invoking `openags/paper-search-mcp` from an installed Codex plugin.
- Whether the paper wiki initializer should be a skill, script, or both.
- Exact MinerU LaTeX output availability and naming contract.
- First-pass reader model and prompt format.
- Whether Zotero sync is included in MVP or deferred.

These are implementation questions, not design blockers, except that the `paper-search-mcp` wrapper contract must be settled before Phase 1 is considered complete.
