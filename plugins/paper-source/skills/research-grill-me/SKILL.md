---
name: research-grill-me
description: >
  Use when the user asks Paper Source / PS to clarify a research direction, refine a vague research
  question, build a Research Brief, produce a deep-research prompt, "研究简报", "帮我梳理科研方向",
  "强追问科研问题", or prepare a formal Paper Source search.
---

# Research Grill

Use this to turn an under-specified research direction into a confirmed Paper Source Research Brief plus a chat-visible general deep-research prompt. Be demanding but efficient: ask one decision point per turn, give a recommended answer, and explain why the decision affects Paper Source.

## Contract

- First read config and repository state instead of asking when the answer is discoverable.
- Ask strong questions with one decision point per turn; each turn includes a recommended answer.
- Explain why the decision affects Paper Source query planning, source scope, ranking, or handoff gates.
- Use no fixed round count; stop when the minimum complete brief can be produced.
- Before creating a confirmed brief, show a Chinese confirmation summary and a chat-visible general deep-research prompt, then require explicit user confirmation.
- The deep-research prompt is companion copy for the user; it does not replace `research-brief.json`, `research-brief.md`, `agent-brief.md`, or downstream Paper Source commands.
- `research-brief.md` is user-facing Chinese; `agent-brief.md` is English.
- Create artifacts only with `research-brief create --answers-json <answers.json> --vault <vault>`.
- Route formal discovery through `dry-run --from-brief <research-brief.json>`.
- Do not write Paper Wiki formal pages directly from a Research Brief.

## Boundaries

Use current names: Paper Source for source discovery/staging and Paper Wiki for formal wiki writing. Old EPI/PRW names are legacy-only when explaining existing artifacts.

Paper Source uses `paper-search-mcp` for paper search. A Research Brief may guide discovery, but it cannot bypass source-staging, `wiki-ingest-brief.json`, human approval, or Paper Wiki handoff gates.

For field schema, defaults, and confirmation wording, load `references/research-brief-contract.md`.
