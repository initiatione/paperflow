# Implementation Plan

1. Add tests for current query-planning weak cases.
2. Update `paper-discovery` skill docs and references so the agent is required to compile related matching terms before MCP search.
3. Add query-plan diagnostics for underspecified variants and missing hard anchors.
4. Improve term expansion through config, Research Brief, and LLM agent-plan fields, without adding local semantic or embedding dependencies.
5. Improve lexical relevance scoring and false-positive handling.
6. Record all new decisions in `query-plan.json` and ranking artifacts.
7. Update Paper Source discovery docs and routing references if behavior changes.
8. Run discovery and contract tests.

## Validation Commands

```powershell
python -m pytest tests\paper_source -q
python -m pytest tests\paper_source\test_skill_bundle_contract.py tests\test_marketplace_manifest.py -q
git diff --check
```

## Resolved Decision

Do not add optional local semantic reranking or new model dependencies. Require the current LLM agent to generate related matching terms in real time and require Paper Source scripts to validate and record those terms.
