# Source Tiers For Engineering Paper Discovery

EPI uses source tiers to avoid treating one search transport as the definition of quality. Prefer structured academic metadata first, then use publisher/web sources for verification and recall gaps.

## Tier Definitions

| Tier | Meaning | Use |
| --- | --- | --- |
| T1 | Structured academic metadata with stable identifiers | First pass search, DOI/arXiv/title normalization, citation metadata |
| T2 | Domain venue or publisher pages with useful metadata | Verify venue, acceptance venue, PDF/code, recent online-first papers |
| T3 | Web search, community lists, discussions, manual pages | Last resort for recall gaps; always mark as unverified until confirmed |

## Robotics / Control / Embodied AI Mapping

| Intent | T1 Sources | T2 Verification | T3 / Manual |
| --- | --- | --- | --- |
| Robotics and control papers | arXiv, Semantic Scholar, OpenAlex, CrossRef | IEEE Xplore, ACM DL, Springer, ScienceDirect, journal DOI pages | Google Scholar, lab pages |
| AUV / marine robotics | Semantic Scholar, OpenAlex, CrossRef, arXiv | Ocean Engineering, IEEE/OES, ICRA/IROS/OCEANS pages, publisher DOI pages | project pages, code repos |
| Embodied AI / robot learning | arXiv, Semantic Scholar, OpenAlex | CoRL, RSS, ICRA, IROS, NeurIPS/ICLR/ICML workshop or proceedings pages | OpenReview, lab pages |
| Venue quality verification | OpenAlex/CrossRef venue metadata | official venue or publisher page, RoboWiki-style curated venue database | Zhihu/forum/community discussion only as weak context |

## Venue Quality Prior

For journal/conference quality priors, load `venue-prior.md`. Keep venue prior separate from verified metrics. RoboWiki-style pages are useful as curated robotics venue priors; Zhihu/forum discussions are weak recall hints only.

## Escalation Rules

1. Start with T1 sources via `paper_search_mcp` or configured live search.
2. If accepted candidates are generic, stale, or review-heavy, sharpen queries and rerun.
3. If a candidate looks important but metadata is incomplete, verify through T2 publisher/venue pages.
4. If a high-quality venue family is missing from results, use T3/manual sources only to identify possible recall gaps, then verify back through T1/T2.
5. In user output, mark unverified quality metrics as `未核实` rather than guessing.
