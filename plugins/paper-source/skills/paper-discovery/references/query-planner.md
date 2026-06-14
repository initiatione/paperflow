# Query Planner

Use the query planner before the first search whenever the user asks for high-quality, latest, non-review, or domain-specific papers. It turns a vague topic into a small, inspectable search plan.

## Required Plan Fields

| Field | Meaning |
| --- | --- |
| `research_mode` | Intent route such as `targeted-discovery`, `quick-brief`, `lit-review`, `systematic-review`, `fact-check`, or `guided` |
| `domain` | `profile-derived` by default when config has a user profile; explicit packs are only optional hints |
| `profile` | The config fields used to derive search terms: profile name, domains, positive/negative keywords, venue prior |
| `concept_blocks` | Profile terms, domain terms, `domain_focus_terms`, method/topic terms, problem terms, context terms, quality signals, and exclusions |
| `query_variants` | 5-8 query variants, written as short academic searches derived by agent analysis from config/profile plus the request topic |
| `source_route` | T1/T2/T3 sources to search and what each source is expected to contribute |
| `recall_gap_checks` | Venue families, citation graph checks, and missing-source checks to run if first results look weak |
| `quality_signals` | Evidence terms that should raise ranking priority |
| `request_constraints` | Agent-supplied executable constraints such as `year_min` and `code_policy` (`ignore`, `prefer`, or `require`) |

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
python scripts\orchestrator.py dry-run --query "<natural language topic>" --query-variant "\"<domain object>\" \"<task>\" \"<method>\" -review -survey" --query-variant "\"<domain object>\" \"<task>\" code -review -survey" --domain-focus-term "<domain object>" --year-min 2021 --code-policy prefer --vault <vault> --json
python scripts\orchestrator.py dry-run --query "<natural language topic>" --agent-query-plan-json <agent-query-plan.json> --vault <vault> --json
```

`--query` remains the intent label and resume signature input. `--query-variant` is what gets sent to `paper_search_mcp`. `--domain-focus-term` is a hard filter anchor when the requested object/domain must be present. `--year-min` rejects older or undated candidates when a recent window is explicit. `--code-policy prefer` ranks public-code candidates higher without dropping otherwise strong papers; `--code-policy require` rejects candidates without a metadata `code_url` / repository identity.

Structured agent plan files should be small, discipline-neutral JSON objects:

```json
{
  "schema_version": "paper-source-agent-query-plan-v1",
  "query_variants": [
    "\"<domain object>\" \"<task>\" \"<method>\" -review -survey",
    "\"<domain object>\" \"<task>\" code -review -survey"
  ],
  "domain_focus_terms": ["<domain object>", "<domain synonym>"],
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
7. Do not encode topic-specific natural-language understanding in Python. If a request says, in Chinese or English, "AUV attitude control, modern control or RL, recent five years, code preferred", the agent should compile terms such as AUV/autonomous underwater vehicle, attitude/orientation control, MPC/sliding-mode/adaptive/robust/nonlinear control, reinforcement learning, code/GitHub, and `year_min` / `code_policy` constraints for this run; the script should record and execute those terms, not own that ontology.
8. Treat query-plan expansion terms as recall aids, not ranking requirements. Ranking/profile fit should use configured interests plus the current topic focus terms, so broad recall terms do not demote a precise, high-quality paper.
9. For narrow requests, compute `domain_focus_terms` before filtering. Prefer request/config terms that identify the object, task, disease, material, platform, organism, venue family, or application domain; broad method family phrases such as reinforcement learning, graph neural network, deep learning, or generic AI are recall/method terms, not enough to pass the hard domain gate by themselves.
10. When the agent supplies hard domain anchors, use those explicit terms and the user's configured domain terms as the hard gate. Do not promote broad n-grams sliced from a long query, such as generic vehicle/task phrases, into `domain_focus_terms` if they would let adjacent but off-domain papers pass without the requested object/domain anchor.
