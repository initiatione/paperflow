# Engineering Paper Intelligence Plugin Design

Date: 2026-05-27
Status: design-review
Owner: initiatione
Repository: `D:\paper-search`

## Purpose

Build a Codex marketplace-installable plugin for engineering literature intelligence. The plugin should search for high-quality papers in user-defined domains, first targeting robotics, AI, embodied intelligence, and control; collect and preserve raw paper assets; parse PDFs through MinerU; produce agent-readable reader outputs; critic-check the outputs; and promote only verified knowledge into a dedicated LLM Wiki vault.

This is not a single skill and not a local script bundle. It is a plugin that packages skills, MCP wiring, scripts, templates, and documentation into an installable workflow.

## Confirmed Decisions

- Plugin name target: `engineering-paper-intelligence`.
- Search layer wraps mature infrastructure, primarily `openags/paper-search-mcp`, instead of rebuilding every source adapter from scratch.
- The existing `mineru-paper-parser` capability becomes one stage inside the larger plugin.
- A new paper-specific wiki vault must be created at `D:\paper-research-wiki`.
- The plugin must not write paper workflow data into the existing `D:\Obsidian-wiki`.
- The paper wiki follows the Ar9av/LLM Wiki pattern: raw source -> compiled wiki -> schema.
- Raw PDF, MinerU Markdown, LaTeX, images, metadata, reader output, critic output, and run records must be retained.
- The full pipeline is automated through a state machine. The agent reads `run-state.json` and routes to MCP, scripts, or skills based on missing artifacts and current state.
- The state machine may skip or reorder stages when that better satisfies the user's goal, but every deviation must be recorded.
- The critic layer is a hard quality gate before compiled wiki writes.
- Hard rule: no critic pass, no compiled wiki write.
- The workflow supports `dry-run`, budget controls, human gates, rollback, redo, and recritic.
- Self-evolution is skill-aware, evidence-backed, staged, and reversible.
- `skill-aware-evolve` never edits plugin code directly. It first proposes changes to controlled assets.

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

The plugin does not own:

- The user's Zotero database.
- The user's existing general-purpose `D:\Obsidian-wiki`.
- Raw paper truth beyond preserving source artifacts.
- Automatic modification of plugin source code during normal operation.

## Plugin Structure

Target plugin layout:

```text
plugins/engineering-paper-intelligence/
  .codex-plugin/
    plugin.json
  .mcp.json
  skills/
    paper-discover/
    paper-normalize/
    paper-filter/
    engineering-paper-ranker/
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
  vendor-notices/
```

The plugin directory contains distributable logic and templates only. Runtime paper data lives in the configured paper wiki and run directories.

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

### critic

Runs quality gates before formal wiki write. It produces critic reports.

Sub-critics:

- `paper-quality-critic`: checks paper quality and collection worthiness.
- `parse-quality-critic`: checks PDF parsing completeness, missing images, broken formulas, and layout issues.
- `reader-quality-critic`: checks summary fidelity, hallucination risk, missed contributions, overstated claims, and unsupported inferences.

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

Feedback updates run records and may generate evolution proposals.

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

MVP should implement:

- Plugin scaffold for `engineering-paper-intelligence`.
- MCP wrapping or invocation path for `openags/paper-search-mcp`.
- `configure -> discover -> normalize -> filter -> rank` dry-run.
- MinerU parser integration migrated from current plugin.
- Dedicated paper wiki initialization template.
- `parse -> read -> critic -> staging` for selected papers.
- Manual-gated `promote-to-wiki`.
- Run-state routing and report.

Post-MVP:

- Zotero sync.
- Automatic recurring digest.
- Full feedback learning.
- Active evolution application.
- Broader source adapters beyond the wrapped MCP.

## Risks and Mitigations

- Search dependency drift: pin the mature MCP version and record attribution.
- Dirty wiki risk: require critic pass and staging before compiled writes.
- Hallucinated summaries: reader output must be source-grounded and critic-checked.
- Parse corruption: parse critic checks pages, image links, formulas, and layout clues.
- API cost creep: dry-run and budget controls are first-class.
- Rule drift: skill-aware evolution is staged and reversible.
- Overgrown plugin scope: keep search, ranking, parsing, reading, critic, wiki, Zotero, and evolution as separate skills/scripts with explicit contracts.

## Open Implementation Questions

- Exact mechanism for invoking `openags/paper-search-mcp` from an installed Codex plugin.
- Whether the paper wiki initializer should be a skill, script, or both.
- Exact MinerU LaTeX output availability and naming contract.
- First-pass reader model and prompt format.
- Whether Zotero sync is included in MVP or deferred.

These are implementation questions, not design blockers.
