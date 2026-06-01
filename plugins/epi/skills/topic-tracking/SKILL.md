---
name: topic-tracking
description: "Use when tracking an EPI research topic over time, asking what is new since a prior run or date, building a reading backlog, checking breadth coverage, or planning broad-to-deep literature review."
---

# Topic Tracking

Use this as the topic-level layer above per-paper EPI stages. The goal is not "finish one slug"; it is to grow a trustworthy view of a research direction over time.

## Core Rule

Treat every `dry-run`, `rank.json`, `report.json`, `_raw/papers/*/metadata.json`, and wiki-ingest record as part of a longitudinal topic ledger. A topic update should separate net-new papers from already-known papers, then show breadth coverage and the next best reading actions.

## When To Pair Skills

| Situation | Pair with |
| --- | --- |
| New one-off search only | `paper-discovery` |
| Ongoing topic monitoring, "what changed", backlog, coverage | `topic-tracking` + `paper-discovery` |
| Raw acquisition and parse after prioritization | `paper-ingest` or `mineru-paper-parser` |
| Final wiki claim deposition | `wiki-provenance` |

## Workflow

1. Identify the topic boundary: user question, profile/config terms, must-include and must-exclude concepts, and the last covered run/date if available.
2. Inspect prior state before searching: `_runs/index.json`, recent `_runs/<run-id>/report.json`, `rank.json`, `_raw/papers/*/metadata.json`, and existing `research-queue` buckets.
3. Run or inspect discovery. Surface `research_mode`, query variants, source route, `domain_focus_terms`, and `recall_gap_checks`; do not hide query drift behind a ranked list.
4. Build the delta: separate `net_new`, `already_known`, `already_in_library:<slug>`, repeated candidates, and lower-confidence review/survey candidates.
5. Rank the backlog by `quality_tier`, profile/topic fit, stable identity, PDF availability, ranking confidence, novelty against the existing topic ledger, and parse/acquisition readiness.
6. Report breadth before depth: venue/source/year/method family/task/benchmark/citation-cluster coverage, plus missing clusters that need another search or citation snowballing pass.
7. Only then choose depth actions: `prepare-ranked --skip-existing`, reader/critic, wiki handoff, or manual PDF reading when parse fidelity is weak.

## Commands

```powershell
python scripts\orchestrator.py dry-run --query "<topic>" --max-results 20 --vault <vault> --json
python scripts\orchestrator.py report --run-id <run-id> --vault <vault> --json
python scripts\orchestrator.py runs-query --vault <vault> --json
python scripts\orchestrator.py research-queue --vault <vault> --json
python scripts\orchestrator.py prepare-ranked --run-id <run-id> --max-papers 10 --skip-existing --vault <vault> --json
```

If this plugin version has no explicit `--since`, emulate since semantics by comparing the current run against prior run artifacts and `_raw/papers/*/metadata.json`. Use `already_in_library:<slug>` as a hard dedupe signal, not as a hidden filter.

## Output Contract

A topic update should include:

- `Topic delta`: new, already-known, excluded, and uncertain papers.
- `Backlog`: ranked reading order with reasons, not just a top-N list.
- `Coverage`: source/venue/year/method/task/benchmark/citation-cluster breadth and gaps.
- `Depth flags`: parse fidelity, acquisition fallback state, and whether PDF/manual inspection is needed.
- `Evidence`: run id, artifact paths, query plan summary, accepted/rejected counts, and any unverified metrics.

Load `references/coverage-and-backlog.md` for the detailed delta, backlog, coverage, and parse-fidelity checklist.

## Hard Stops

- Do not equate per-paper completion with topic progress.
- Do not report only the newest top paper when the user asked to monitor a direction.
- Do not invent impact factor, JCR quartile, citation count, acceptance rate, or coverage confidence. Mark unverified metrics as unverified.
- Do not let broad query expansion terms become hard topic requirements unless they came from config, current request, or user approval.
