# Ranking Rubric

Use this file when explaining why a candidate was advanced, held for review, or rejected after the dry-run.

## Ranking Layers

EPI ranking is intentionally multi-layered:

1. `ranking_signals`: numeric heuristic signals for topic, venue, citation, freshness, PDF/code, benchmark, reproducibility, and negative keyword overlap.
2. `paper_classification`: title/abstract paper type classification.
3. `ranking_rubric`: human-readable dimensions derived from the signals.
4. `ranking_protocol`: advance/review decision, reasons, cautions, lenses, type, rubric scores, and confidence.
5. `ranking_rationale`: low-reading-burden explanation for the user and downstream wiki route suggestions.

## Rubric Dimensions

| Dimension | Meaning | Useful evidence |
| --- | --- | --- |
| `relevance` | Fit to user profile and current query | positive keywords, domain anchor, negative keyword penalty |
| `method_rigor` | Method and evaluation credibility | benchmark terms, citations, PDF availability |
| `evidence_sufficiency` | Whether claims are inspectable | PDF, benchmark, citations, reproducibility terms |
| `reproducibility` | Engineering follow-up potential | code, dataset, implementation, simulator, config |
| `source_confidence` | Metadata/source confidence | venue prior, citation signal, stable PDF |

## Interpretation Rules

1. Do not publish a single fake precision score as if it were peer-review truth.
2. Treat `ranking_confidence` as a heuristic confidence in the ranking evidence, not a truth probability.
3. Use low confidence to trigger review, sharper rerun, citation-graph expansion, or source verification.
4. Keep venue prior separate from verified metrics such as impact factor, quartile, CiteScore, and citation count.
5. When `paper_type=survey` in a non-review run, explain the exclusion rather than silently promoting it.

## Chat Recommendation Shape

For each kept candidate, include the paper type, ranking rationale, strongest evidence, and caveat. Avoid long abstracts; point to the EPI run artifacts for audit.
