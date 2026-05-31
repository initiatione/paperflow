# Query Planner

Use the query planner before the first search whenever the user asks for high-quality, latest, non-review, or domain-specific papers. It turns a vague topic into a small, inspectable search plan.

## Required Plan Fields

| Field | Meaning |
| --- | --- |
| `domain` | `profile-derived` by default when config has a user profile; explicit packs are only optional hints |
| `profile` | The config fields used to derive search terms: profile name, domains, positive/negative keywords, venue prior |
| `concept_blocks` | Profile terms, domain terms, method/topic terms, problem terms, context terms, quality signals, and exclusions |
| `query_variants` | 5-8 query variants derived from config/profile plus the request topic |
| `source_route` | T1/T2/T3 sources to search and what each source is expected to contribute |
| `recall_gap_checks` | Venue families, citation graph checks, and missing-source checks to run if first results look weak |
| `quality_signals` | Evidence terms that should raise ranking priority |

## Helper

The bundled helper is deterministic and network-free:

```powershell
python skills\paper-discovery\scripts\query-planner.py --topic "<topic>" --domain auto --max-queries 8
python skills\paper-discovery\scripts\query-planner.py --topic "<review topic>" --domain auto --include-reviews --max-queries 8
python skills\paper-discovery\scripts\query-planner.py --topic "<topic>" --domain profile --profile "<profile>" --domains "<domain1>,<domain2>" --positive-keywords "<term1>,<term2>" --venue-prior "<venue1>,<venue2>" --max-queries 8
```

Use it when the user gives a compact request. The helper output is a starting point; agent judgment still decides whether to add task-specific terms or ask the user to improve config.

## Planning Rules

1. Start from `_meta\epi-config.yaml`: profile, domains, positive_keywords, negative_keywords, and venue_prior.
2. Generate both broad and narrow queries: broad queries catch recall, narrow queries catch precision.
3. Include evidence terms appropriate to the user's field, such as benchmark, experiment, dataset, field study, code, replication, or domain-specific validation terms.
4. Default discovery is non-review: append `-review -survey` to every query and still enforce review exclusion in filtering. Skip this only when the user explicitly asks for review or survey papers.
5. If the plan produces fewer than 5 strong variants, expand from the user's configured field vocabulary before broadening into generic AI/science terms.
6. Domain hint packs such as AUV/control or embodied AI are examples only. They must activate from explicit user request/config, never as global plugin defaults.
7. Treat query-plan expansion terms as recall aids, not ranking requirements. Ranking/profile fit should use configured interests plus the current topic focus terms, so broad recall terms do not demote a precise, high-quality paper.
