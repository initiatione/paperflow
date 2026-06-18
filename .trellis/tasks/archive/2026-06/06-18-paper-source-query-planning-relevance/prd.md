# Paper Source Query Planning Relevance

## Goal

Improve how Paper Source turns natural-language requests plus user config into precise MCP searches and relevance filtering, so retrieval is less dependent on agent luck.

## Confirmed Facts

- `build_query_plan` generates query variants from config and topic terms.
- The deterministic planner uses lightweight n-grams and generic quality terms.
- Agent-supplied query variants and hard anchors are supported, but the script does not strongly validate that a complex request produced a sufficiently specific query plan.
- The current ranking relevance layer uses substring matching over title and abstract.

## Requirements

- Make query planning visibly consume config domains, positive keywords, negative keywords, venue prior, Research Brief anchors, and request constraints.
- Update Paper Source discovery skill instructions so the AI agent must analyze the user request and produce explicit matching terms before MCP search.
- Add query-plan quality diagnostics that flag raw or underspecified natural-language searches when stronger variants or hard anchors are expected.
- Improve acronym/synonym handling through config, Research Brief, or agent-plan fields without hardcoding one field.
- Separate hard domain anchors from soft recall terms and preserve term provenance in artifacts.
- Improve relevance scoring beyond exact substring matching through LLM-compiled query-plan terms and deterministic validation. Do not introduce local semantic reranking, embeddings, vector search, or new model dependencies.
- Keep MCP provider routing compatible with current `paper_search_mcp` and optional Grok supplemental behavior.

## Acceptance Criteria

- [ ] A complex natural-language request creates multiple explicit query variants, not only the raw request.
- [ ] Query-plan artifacts show which terms came from config, user request, Research Brief, or agent input.
- [ ] Tests cover acronym/synonym expansion from config or an agent query plan.
- [ ] Tests cover negative keyword exclusion and hard-anchor filtering.
- [ ] Relevance ranking avoids obvious substring false positives in at least one fixture by using LLM-compiled terms, hard anchors, exclusions, provenance, or deterministic lexical checks.
- [ ] Provider routing still treats Grok as supplemental and does not present Grok-only results without the existing paper-search anchor policy.

## Resolved Decision

- Do not use optional local semantic reranking. The current LLM agent is responsible for real-time request analysis and related-term generation; Paper Source scripts are responsible for deterministic validation, execution, artifact provenance, and regression gates.
- The skill should guide the agent to produce query variants, hard anchors, soft recall terms, acronym expansions, exclusions, provenance, and confidence notes before retrieval.
