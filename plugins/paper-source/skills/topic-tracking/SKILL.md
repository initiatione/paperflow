---
name: topic-tracking
description: >
  Use when tracking Paper Source topics: "持续跟踪这个方向", "最近有什么新论文", backlog, coverage, since.
---

# Topic Tracking

Use this topic-level layer above per-paper stages. Goal: grow a trustworthy view of a research direction over time, not finish one slug. If profile/config context is missing, route to `config-setup`; see `docs\config.md`.

## Core Rule

Treat every `dry-run`, `rank.json`, `report.json`, `_paper_source/raw/*/metadata.json`, and wiki-ingest record as the topic ledger. Separate net-new from known papers, then show coverage and next reading actions.

## Pairing

- New one-off search: `paper-discovery`.
- Ongoing monitoring, "what changed", backlog, or coverage: `topic-tracking` + `paper-discovery`.
- Raw acquisition and parse after prioritization: `paper-ingest` or `mineru-paper-parser`.
- Final wiki claim deposition: `wiki-provenance`.

## Workflow

1. Identify boundary: user question, config/profile terms, must-include/exclude concepts, last covered run/date.
2. Inspect prior state before searching: `_paper_source/runs/index.json`, recent reports/ranks, `_paper_source/raw/*/metadata.json`, and `research-queue`.
3. Run or inspect discovery; surface `research_mode`, query variants, source route, `domain_focus_terms`, and `recall_gap_checks`.
4. Build delta: `net_new`, `already_known`, `already_in_library:<slug>`, repeats, uncertain review/survey candidates.
5. Rank backlog by quality tier, topic fit, identity, PDF availability, confidence, novelty, and parse/acquisition readiness.
6. Report coverage before depth: venue/source/year/method/task/benchmark/citation-cluster breadth and missing clusters.
7. Choose depth actions: `prepare-ranked --skip-existing`, reader/critic, wiki handoff, or manual PDF reading when parse fidelity is weak.

## Commands

```powershell
python scripts\orchestrator.py dry-run --query "<topic>" --max-results 20 --vault <vault> --json
python scripts\orchestrator.py report --run-id <run-id> --vault <vault> --json
python scripts\orchestrator.py runs-query --vault <vault> --json
python scripts\orchestrator.py research-queue --vault <vault> --json
python scripts\orchestrator.py prepare-ranked --run-id <run-id> --max-papers 10 --skip-existing --vault <vault> --json
```

If no explicit `--since` exists, emulate it by comparing current run artifacts against prior runs and `_paper_source/raw/*/metadata.json`. Use `already_in_library:<slug>` as a hard dedupe signal, not a hidden filter.

## Output Contract

Include `Topic delta`, `Backlog`, `Coverage`, `Depth flags`, and `Evidence` with run id, artifact paths, query plan summary, accepted/rejected counts, and unverified metrics. Load `references/coverage-and-backlog.md` for the detailed checklist.

## Hard Stops

- Do not equate per-paper completion with topic progress.
- Do not report only the newest top paper when the user asked to monitor a direction.
- Do not invent impact factor, JCR quartile, citation count, acceptance rate, or coverage confidence. Mark unverified metrics as unverified.
- Do not let broad query expansion terms become hard topic requirements unless they came from config, current request, or user approval.
