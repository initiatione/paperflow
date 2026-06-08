# EPI Discovery Mode Routing

Use this file when the request is broader than a single `dry-run` command or when the user asks for a literature review, systematic review, fact-checking, or guided research scoping.

## Modes

| Mode | Use when | EPI behavior | Human oversight |
| --- | --- | --- | --- |
| `targeted-discovery` | Default for finding high-quality papers on a clear topic | Build `query-plan.json`, search variants, filter, classify, rank, and report reading priority | Medium |
| `quick-brief` | User asks for a compact scan or 30-minute summary | Run a smaller dry-run, summarize all kept papers, and call out recall gaps | Medium |
| `lit-review` | User explicitly asks for a literature review, survey, or annotated bibliography | Do not hard-exclude reviews/surveys; separate survey papers from method/system papers | Medium |
| `systematic-review` | User asks for PRISMA, meta-analysis, or systematic review | Use EPI only to build and screen the corpus; require explicit inclusion/exclusion criteria before any final synthesis | High |
| `fact-check` | User provides claims or wants evidence verification | Prefer source-first paper ingest or targeted source lookup over broad discovery | Medium |
| `guided` | User has a vague direction and wants help thinking | Ask one scoping question or propose 2-3 concrete query routes before running broad discovery | Very high |

## Routing Rules

1. Prefer `targeted-discovery` when the user gives a clear paper topic and does not request a review/survey.
2. If the user says `not review`, `no survey`, or equivalent, keep `targeted-discovery` even though the word `review` appears in the request.
3. `lit-review` and `systematic-review` may include review/survey/meta candidates, but must label them separately from primary method/system papers.
4. `fact-check` should not produce a broad reading list unless the claim cannot be checked from the provided or known sources.
5. `guided` should converge quickly into a concrete discovery command; do not turn EPI into a long research-coaching session.

## Output Contract

`query-plan.json` and `report.json.discovery_context` should expose `research_mode` so later agents know whether the run was a default discovery, review-oriented search, fact-check, quick brief, or guided setup.
