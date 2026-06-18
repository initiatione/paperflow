# Ranking Rubric

Use this file when explaining why a candidate was advanced, held for review, or rejected after the dry-run.

## Ranking Layers

Paper Source ranking is intentionally multi-layered:

1. `ranking_signals`: numeric heuristic signals for topic, venue, EasyScholar `easyscholar_score`, citation, freshness, PDF/code, benchmark, reproducibility, quality risk, and negative keyword overlap. Topic diagnostics include `topic_fit_basis`, `keyword_topic_score`, `keyword_coverage_score`, and priority/positive keyword counts so long profiles are visible without becoming an accidental hard denominator.
2. `paper_classification`: title/abstract paper type classification.
3. `quality_gate`: Tier A/B/C/Reject gate with stable identity, PDF, topic-fit, venue, citation, benchmark, reproducibility, blocking/caution evidence, and cross-discipline `dimensions`.
4. `ranking_rubric`: human-readable dimensions derived from the signals.
5. `ranking_protocol`: advance/review decision, quality tier, reasons, cautions, lenses, type, rubric scores, and confidence.
6. `ranking_rationale`: low-reading-burden explanation for the user and downstream wiki route suggestions.

## Rubric Dimensions

| Dimension | Meaning | Useful evidence |
| --- | --- | --- |
| `relevance` | Fit to user profile and current query | positive keywords, domain anchor, negative keyword penalty |
| `method_rigor` | Method and evaluation credibility | benchmark terms, citations, PDF availability |
| `evidence_sufficiency` | Whether claims are inspectable | PDF, benchmark, citations, reproducibility terms |
| `reproducibility` | Engineering follow-up potential | code, dataset, implementation, simulator, config |
| `source_confidence` | Metadata/source confidence | venue prior, EasyScholar verified metrics, citation signal, stable PDF |

## Quality Gate Dimensions

`quality_gate.dimensions` is the compact machine-readable explanation for why a paper passed, stayed in review, or was rejected. It is intentionally discipline-neutral:

| Dimension | Meaning |
| --- | --- |
| `identity` | DOI/arXiv or other stable bibliographic identity |
| `relevance` | Topic fit and `topic_fit_basis` (`priority_keywords` or `positive_keywords_saturated`) |
| `inspectability` | PDF/source availability for evidence inspection |
| `validation` | Benchmark, citation, or reproducibility support |
| `source_confidence` | Venue, citation, PDF, and verified metric confidence |
| `reproducibility` | Code/data/reproducibility evidence |
| `request_risk` | Negative keyword or explicit request conflict risk |
| `quality_risk` | Provider evidence for retraction, withdrawal, expression-of-concern, paper-mill, or predatory-venue risk; missing evidence is `unverified` |

## Interpretation Rules

1. Do not publish a single fake precision score as if it were peer-review truth.
2. Treat `ranking_confidence` as a heuristic confidence in the ranking evidence, not a truth probability.
3. Use low confidence to trigger review, sharper rerun, citation-graph expansion, or source verification.
4. Keep venue prior separate from verified metrics such as impact factor, quartile, CiteScore, and citation count.
5. Do not let venue prior or `verified_metrics.easyscholar` alone create `quality_tier=Tier A`; Tier A also needs stable identity, PDF, topic fit, and validation evidence.
6. When `paper_type=survey` in a non-review run, explain the exclusion rather than silently promoting it.
7. EasyScholar writes `easyscholar-record.json` and `verified_metrics.easyscholar` when available. If `EASYSCHOLAR_SECRET_KEY` is missing, disabled with `--no-easyscholar`, or the API cannot verify the venue, report the metric as `未核实`.
8. When `priority_keywords` are present, use them as the relevance gate basis. When they are absent, use the saturated positive-keyword topic score for relevance and keep `keyword_coverage_score` as diagnostics only.
9. `paper-search-mcp` result ordering is source/provider evidence, not the final ranking rubric. Paper Source owns ranking, quality tiers, DOI policy, and recommendation surfaces.
10. Verified severe `quality_risk` evidence lowers recommendation eligibility through `verified_quality_risk`; suspected or missing risk data must remain visible as cautions without silently rejecting the paper.

## Chat Recommendation Shape

For each kept candidate, include the paper type, ranking rationale, strongest evidence, and caveat. Avoid long abstracts; point to the Paper Source run artifacts for audit.
