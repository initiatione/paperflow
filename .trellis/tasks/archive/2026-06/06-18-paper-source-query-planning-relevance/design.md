# Design

## Boundary

This task owns query-plan construction, query-plan diagnostics, and relevance scoring before or during ranking. It must not change provider authentication, Paper Source/Paper Wiki boundaries, or final wiki writing behavior.

## Planner Contract

`query-plan.json` should show:

- request intent
- config-derived terms
- Research Brief terms
- user/agent hard anchors
- soft recall terms
- exclusions
- term provenance
- query variants actually sent to MCP providers
- diagnostics when the plan is too broad or too raw

## Relevance Contract

Default relevance must remain deterministic and dependency-light. Do not add local embedding or semantic-reranker dependencies.

The current LLM agent should do semantic analysis before calling the script, then pass explicit query-plan material:

- synonyms and related terms
- acronym expansions
- hard domain anchors
- soft recall terms
- exclusions and negative concepts
- query variants
- term provenance and confidence notes

The script should validate, record, and execute this plan. It should flag weak plans instead of trying to replace the agent with a local model.

## Skill Contract

The Paper Source discovery skill should instruct the agent to:

1. Read the user request and Paper Source config.
2. Expand the request into field-specific matching terms, synonyms, acronyms, negative terms, hard anchors, and soft recall terms.
3. Prefer `--agent-query-plan-json` or explicit `--query-variant` / `--domain-focus-term` inputs for complex requests.
4. Record provenance for why each term exists.
5. Treat raw natural-language search as a fallback, not the primary path.

The script should not trust the skill blindly. It should emit diagnostics when the plan is missing, too broad, or fails to use available config signals.

## Provider Routing

Paper-search remains primary. Grok remains supplemental and subject to the existing anchor policy.
