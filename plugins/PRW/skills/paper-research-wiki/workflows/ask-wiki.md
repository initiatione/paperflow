# Ask Wiki Workflow

Use this workflow for user research questions such as `提问`, `问 wiki`, `问论文 wiki`, `根据 wiki 回答`, `查询论文 wiki`, `ask wiki`, `ask paper wiki`, `what does the wiki say`, and `research question`.

This workflow is read-only. Use no `log.md` writes: do not write `log.md`, do not write formal pages, do not refresh QMD, and do not write EPI artifacts.

## Flow

Question -> Scope -> Formal graph retrieval -> Evidence check -> Answer labels -> Correction candidates -> Stop

1. Scope the question into research objects, tasks, methods, metrics, and uncertainty. Keep the original wording so the answer can show what was searched.
2. Retrieve from the formal Obsidian graph first: `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/`.
3. Use Obsidian graph signals, not only keyword search. Expand exact hits through backlinks, outlinks, reciprocal links, aliases, tags, and co-links. Prefer directly related formal pages over loose lexical matches.
4. Use `_epi/raw` only as source evidence when formal pages need confirmation. Do not treat `_epi/**` as formal graph pages.
5. QMD is an optional accelerator. When qmd query is available and likely to reduce search cost, it may be used to find candidate pages, then the candidates must be verified against Markdown formal pages or source evidence. If QMD is unavailable, stale, slow, or noisy, fallback to frontmatter, `index.md`, `hot.md`, manifest files, and direct Markdown search.
6. Answer with these labels:
   - `【Wiki 证据】`: claims directly supported by returned formal pages or checked source evidence.
   - `【综合判断】`: cross-page synthesis from multiple wiki pages.
   - `【推断】`: AI reasoning beyond directly stated wiki claims; mark it as inference.
   - `【边界/不确定】`: missing evidence, weak provenance, stale links, or unresolved scope.
7. Track correction candidates during retrieval. Include broken wikilinks, ambiguous aliases, duplicate concept owners, stale tracking links, forbidden `_epi/**` graph links, source/frontmatter mismatch, and relationship direction mistakes.
8. Stop after the answer. Report correction candidates and ask before repair. Do not route to update, relink, redo, `record-wiki-ingest`, `prw-record-request.json`, or any write workflow until the user confirms.

## Output Contract

Include:

- the scoped question,
- the formal pages and graph signals used,
- answer sections labeled `【Wiki 证据】`, `【综合判断】`, `【推断】`, and `【边界/不确定】`,
- correction candidates, or a statement that none were found,
- a final question asking whether to repair the correction candidates.

Use concise, research-useful prose. Do not paste large page excerpts. When evidence is thin, say what is missing instead of overstating the answer.
