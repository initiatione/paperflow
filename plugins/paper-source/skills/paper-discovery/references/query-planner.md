# Query Planner

Use the query planner before the first search whenever the user asks for high-quality, latest, non-review, or domain-specific papers. It turns a vague topic into a small, inspectable search plan.

## Required Plan Fields

| Field | Meaning |
| --- | --- |
| `research_mode` | Intent route such as `targeted-discovery`, `quick-brief`, `lit-review`, `systematic-review`, `fact-check`, or `guided` |
| `domain` | `profile-derived` by default when config has a user profile; explicit packs are only optional hints |
| `profile` | The config fields used to derive search terms: profile name, domains, positive/negative keywords, venue prior |
| `concept_blocks` | Profile terms, domain terms, `hard_domain_anchors`, `soft_recall_terms`, method/topic terms, problem terms, context terms, quality signals, and exclusions |
| `query_variants` | 5-8 query variants, written as short academic searches derived by agent analysis from config/profile plus the request topic |
| `source_route` | T1/T2/T3 sources to search and what each source is expected to contribute |
| `recall_gap_checks` | Venue families, citation graph checks, and missing-source checks to run if first results look weak |
| `quality_signals` | Evidence terms that should raise ranking priority |
| `request_constraints` | Agent-supplied executable constraints such as `year_min` and `code_policy` (`ignore`, `prefer`, or `require`) |
| `selection_policy` | Ranking-to-staging policy such as `balanced_high_quality`, `strict_advance`, or `code_required` |
| `term_provenance` | Per-term origin: user/config/Research Brief hard anchor or agent/topic soft recall |

## Helper

The bundled helper is deterministic and network-free:

```powershell
python skills\paper-discovery\scripts\query-planner.py --topic "<topic>" --domain auto --max-queries 8
python skills\paper-discovery\scripts\query-planner.py --topic "<review topic>" --domain auto --include-reviews --max-queries 8
python skills\paper-discovery\scripts\query-planner.py --topic "<topic>" --domain profile --profile "<profile>" --domains "<domain1>,<domain2>" --positive-keywords "<term1>,<term2>" --venue-prior "<venue1>,<venue2>" --max-queries 8
```

Use it when the user gives a compact request. The helper output is a starting point; agent judgment still decides whether to add task-specific terms, translate multilingual intent, split method branches, or ask the user to improve config.

For complex natural-language topics, prefer explicit agent-supplied variants:

```powershell
python scripts\orchestrator.py dry-run --query "<natural language topic>" --query-variant "\"<domain object>\" \"<task>\" \"<method>\" -review -survey" --query-variant "\"<domain object>\" \"<task>\" code -review -survey" --domain-focus-term "<domain object>" --year-min 2021 --code-policy prefer --selection-policy balanced_high_quality --vault <vault> --json
python scripts\orchestrator.py dry-run --query "<natural language topic>" --agent-query-plan-json <agent-query-plan.json> --vault <vault> --json
```

`--query` remains the intent label and resume signature input. `--query-variant` is what gets sent to `paper_search_mcp`. `--domain-focus-term` is a hard filter anchor when the requested object/domain must be present. In agent plan JSON, legacy `domain_focus_terms` are soft recall; use `hard_domain_anchors` or `hard_constraints` for hard filters. `--year-min` rejects older or undated candidates when a recent window is explicit. `--code-policy prefer` ranks public-code candidates higher without dropping otherwise strong papers; `--code-policy require` rejects candidates without a metadata `code_url` / repository identity.

Structured agent plan files should be small, discipline-neutral JSON objects:

```json
{
  "schema_version": "paper-source-agent-query-plan-v1",
  "query_variants": [
    "\"<domain object>\" \"<task>\" \"<method>\" -review -survey",
    "\"<domain object>\" \"<task>\" code -review -survey"
  ],
  "hard_domain_anchors": ["<domain object>", "<domain synonym>"],
  "soft_recall_terms": ["<agent inferred expansion>"],
  "term_provenance": {
    "<domain object>": "user_explicit_hard_anchor",
    "<agent inferred expansion>": "agent_inferred_soft_recall"
  },
  "year_min": 2021,
  "code_policy": "prefer",
  "concept_blocks": {
    "task_terms": ["<task>"],
    "method_branches": ["<method family>"],
    "quality_signals": ["code", "experiment"]
  }
}
```

The script validates, records, filters, and ranks from these fields; it does not infer field-specific vocabulary from the raw natural-language topic.

## Planning Rules

1. Start from `_paper_source\meta\paper-source-config.yaml`: profile, domains, positive_keywords, negative_keywords, and venue_prior.
2. Generate both broad and narrow queries: broad queries catch recall, narrow queries catch precision.
3. Include evidence terms appropriate to the user's field, such as benchmark, experiment, dataset, field study, code, replication, or domain-specific validation terms.
4. Default discovery is non-review: append `-review -survey` to every query and still enforce review exclusion in filtering. Skip this only when the user explicitly asks for review or survey papers.
5. If the plan produces fewer than 5 strong variants, expand from the user's configured field vocabulary before broadening into generic AI/science terms.
6. Do not ship executable discipline packs in the query planner. AUV, robotics, medicine, materials, chemistry, social science, or any other field vocabulary must come from user config, the current request, a Research Brief, or explicit agent-supplied `--query-variant` / `--domain-focus-term` / `--agent-query-plan-json` inputs.
7. Do not encode topic-specific natural-language understanding in Python. If a request says, in Chinese or English, "AUV attitude control, modern control or RL, recent five years, code preferred", the agent should plan terms such as AUV/autonomous underwater vehicle, attitude/orientation control, MPC/sliding-mode/adaptive/robust/nonlinear control, reinforcement learning, code/GitHub, and `year_min` / `code_policy` constraints for this run; the script should record and execute those terms, not own that ontology.
8. Treat query-plan expansion terms as recall aids, not ranking requirements. Ranking/profile fit should use configured interests plus the current topic focus terms, so broad recall terms do not demote a precise, high-quality paper.
9. For narrow requests, compute `hard_domain_anchors` before filtering only when the object, task, disease, material, platform, organism, venue family, or application domain is explicit in the user request, config, or Research Brief. Broad method family phrases such as reinforcement learning, graph neural network, deep learning, or generic AI are recall/method terms, not hard anchors by themselves.
10. Do not promote broad n-grams sliced from a long query into hard filters. Put inferred expansions in `soft_recall_terms`; the script records them in `discovery-diagnostics.json` for recall analysis.
