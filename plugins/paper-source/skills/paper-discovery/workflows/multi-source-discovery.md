# Workflow: Multi-Source Academic Paper Discovery

Use this workflow when the user asks for high-quality papers, latest papers, non-review papers, or any topic defined by the user's Paper Source profile/config.

## Procedure

1. Analyze topic into concept blocks:
   - configured discipline/domain object
   - method or topic family
   - problem, task, population, system, material, dataset, or phenomenon
   - context, environment, setting, or constraints
   - validation mode, such as experiment, field study, dataset, benchmark, proof, replication, or code
   - exclusions, especially review/survey when requested
2. Build a query plan by `query-planner.md`; use config first and `domain-ontology.md` only as optional examples for synonyms, exclusions, and evidence terms.
3. Build 5-8 query variants from agent analysis of the user request. Include exact phrases, acronym expansions, task/method branches, code or benchmark evidence terms when requested, and `-review -survey` unless reviews are explicitly requested.
   - If the user specifies recent papers, public code, or similar executable constraints, pass them as `year_min` and `code_policy` via `--agent-query-plan-json` or CLI flags; do not leave them only in query text.
4. Route sources by `source-tiers.md`.
5. Search T1 sources first through `paper_search_mcp` or configured source adapters by passing the compiled variants with repeated `--query-variant` or `--agent-query-plan-json`; keep the raw user request only as the run intent label.
6. Use `two-stage-retrieval.md`: collect a high-recall candidate pool before precision filtering.
7. Deduplicate by `dedup-engine.md`.
8. Apply venue prior using `venue-prior.md`, then verify venue/citation/DOI/PDF/code and record unverified metrics explicitly.
9. Expand strong seed papers with `citation-graph.md` when latest/high-quality recall matters.
10. Apply `quality-gate.md` to label Tier A/B/C/Reject.
11. If venue priors indicate missing obvious venues or papers, run a sharper rerun and record the recall gap.
12. Present all kept papers using `output-format.md`.

## Venue Prior Step

Classify venue before final ranking using the user's `venue_prior`:

- Use configured journals/conferences/databases and field-curated lists as prior.
- Use community discussions only as weak recall hints or subjective context.
- Verify official venue, publisher page, DOI, citation count, and impact metrics separately.

Do not promote a paper only because a venue is highly ranked. A strong venue with weak topic fit still needs review; a lower-tier venue with real field validation may be valuable for the user's research reading.

## Output Evidence

The final answer should distinguish:

- `query_plan`: concept blocks, query variants, domain anchors, and request constraints used.
- `candidate_pool`: rough size before and after dedup/filter.
- `venue_prior`: community or curated venue tier, if used.
- `verified_metrics`: DOI, citation count, IF/JCR/CiteScore, official venue page, PDF/code.
- `verification_warnings`: fields that are plausible but not confirmed.
- `recall_gap`: important papers or venues discovered outside the first Paper Source result set.
