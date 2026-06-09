# Research Brief Contract

## Minimum Complete Brief

Collect only what Paper Source needs for the current task:

- `slug`: `YYYYMMDD-<topic>` lowercase ASCII kebab-case.
- `title`: short user-facing title.
- `task`: what papers or evidence to find.
- `domain_scope`: hard topical boundaries.
- `specific_questions`: one or more answerable research questions.
- `keywords`: required or high-value search terms.
- `exclusions`: terms, methods, or paper types to avoid.
- `review_policy.type`: `exclude`, `include`, or `mixed`.
- `source_scope.type`: one of the Research Brief source scopes, usually `paper_search_mcp_default`.
- `output_goal.type`: reading priorities, staging candidates, literature-review seed, topic-tracking seed, or fact-check sources.
- `unknowns`: explicit gaps that should remain visible.
- `field_sources`: mark whether each field came from user confirmation, config/repo state, or a brief default.

## Questioning Rules

Ask one decision point per turn. Each question must include:

- a recommended answer;
- why the choice affects Paper Source search, ranking, source-staging, or handoff gates;
- a short fallback such as "use the recommendation" when the user does not care.

Read before asking when available:

- `_paper_source/meta/paper-source-config.yaml`;
- recent `_paper_source/research-briefs/*/research-brief.json`;
- relevant `_paper_source/runs/*/report.json` or `search-record.json`;
- current workspace docs or user-provided files.

There is no fixed round count. Continue only until the minimum complete brief is safe to produce.

## Chat Deep-Research Prompt

When the minimum complete brief is safe to present, output a chat-visible general deep-research prompt in the same conversation turn as the Chinese confirmation summary. Use English Markdown headings and fill the content in the user's working language; default to Chinese when the user writes Chinese.

The deep-research prompt is companion copy for reuse in another deep-research tool or manual review. It is not the canonical Paper Source artifact, not a Paper Wiki handoff, and must not be passed to `dry-run` as a freeform query.

Use this template:

```markdown
### TASK

[A clear, concrete statement of what should be researched.]

### CONTEXT/BACKGROUND

[Why this research matters, who will use it, and what decision or workflow it should support.]

### SPECIFIC QUESTIONS OR SUBTASKS

1. [Concrete research question or subtask.]
2. [Concrete research question or subtask.]
3. [Concrete research question or subtask.]

### KEYWORDS

[Required and high-value terms, synonyms, methods, datasets, venues, organisms, systems, or applications.]

### CONSTRAINTS

- Domain scope: [hard topical boundaries]
- Timeframe: [date range or "unspecified"]
- Geography or deployment context: [if relevant]
- Source types: [academic papers, benchmarks, datasets, standards, patents, reports, etc.]
- Exclusions: [terms, methods, paper types, or claims to avoid]
- Unknowns: [gaps that should remain visible rather than guessed]

### OUTPUT FORMAT

- [Expected artifact: report, prioritized paper list, evidence table, reproduction plan, literature-review seed, etc.]
- [Expected depth and length]
- Citation requirements: include author or organization, publication date, source title, URL or DOI, and page/section/figure locator when available.

### FINAL INSTRUCTIONS

Do not answer from memory alone. Search systematically, compare source quality, mark unsupported claims, and ask for clarification if the task remains ambiguous.
```

## Confirmation And Creation

Before confirmed creation, present a Chinese summary covering task, domain scope, questions, keywords, exclusions, source scope, output goal, and unknowns. Include the chat-visible general deep-research prompt after that summary. Ask for explicit confirmation; do not treat silence or a vague "ok" as confirmation if material fields are still uncertain.

After confirmation, write an answers JSON and run:

```powershell
python scripts\orchestrator.py research-brief create --answers-json <answers.json> --vault <vault> --json
```

The generated `research-brief.md` is Chinese for the user. The generated `agent-brief.md` is English for downstream agents.

## Downstream Boundary

Use the confirmed `research-brief.json` for discovery:

```powershell
python scripts\orchestrator.py dry-run --from-brief <research-brief.json> --vault <vault>
```

Research Briefs override Research Profile for the current task, but they are not Paper Wiki handoffs. They must not write Paper Wiki formal pages directly from a Research Brief. Formal wiki work still goes through source-staging, `wiki-ingest-brief.json`, approval, and Paper Wiki.

Use current terms: Paper Source and Paper Wiki. Old EPI/PRW names are legacy-only if an existing artifact uses them. Paper Source uses `paper-search-mcp`; avoid legacy or alternate backend names.
