# Paper Type Taxonomy

Use this taxonomy when interpreting `rank.json.paper_classification`, curating chat recommendations, or deciding which papers should enter full reading.

## Primary Types

| Type | Typical signal | Reading implication |
| --- | --- | --- |
| `method` | algorithm, model, architecture, controller, policy, framework | Inspect method decomposition, assumptions, baselines, and equations. |
| `system` | system, platform, pipeline, toolkit, simulator, implementation | Inspect components, integration boundary, artifacts, and reproducibility hooks. |
| `benchmark` | benchmark, leaderboard, evaluation suite, baseline comparison | Inspect task definition, metrics, baselines, and whether the benchmark is reusable. |
| `dataset` | dataset, corpus, data collection | Inspect data source, annotation, splits, licensing, bias, and benchmark coupling. |
| `field-trial` | field trial, deployment, hardware experiment, in-the-wild | Prioritize experimental context, safety boundary, and external validity. |
| `theory` | theorem, proof, stability, convergence, theoretical analysis | Preserve formulas, assumptions, proof cues, notation, and applicability limits. |
| `survey` | survey, review, systematic review, literature review, meta-analysis | Use for map-building only unless the user requested review papers. |
| `application` | case study, empirical study, applied evaluation | Inspect domain fit, task realism, and transfer limits. |
| `reproducibility` | reproducible, replication, open-source, replication study | Treat as useful for verification even if novelty is lower. |
| `unknown` | insufficient title/abstract signal | Do not overfit; read metadata and source text before assigning wiki routes. |

## Classification Rules

1. Classify from title/abstract first; source paper reading may refine the type later.
2. Keep `paper_type` as a routing hint, not a hard truth.
3. Use `secondary_types` when a method paper is also a benchmark, dataset, or field trial.
4. Do not let a famous venue override type: a survey in a strong venue is still a survey.
5. When the user asks for non-review papers, `survey` candidates should be rejected or placed outside the recommendation list.

## EPI Fields

`rank.json` candidates should expose:

- `paper_type`
- `classification_confidence`
- `classification_evidence`
- `paper_classification.primary_type`
- `paper_classification.secondary_types`
- `paper_classification.type_scores`
