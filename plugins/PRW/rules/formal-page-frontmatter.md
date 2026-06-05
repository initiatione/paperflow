# Formal Page Frontmatter

Required frontmatter fields: `title`, `category`, `page_family`, `tags`, `aliases`, `sources`, `summary`, `provenance`, `base_confidence`, `lifecycle`, `lifecycle_changed`, `tier`, `created`, and `updated`.

`sources` contains clickable original-paper PDF links only. `references/ pages` use exactly one clickable original-paper PDF link. Canonical form: a Markdown link displayed with the paper title, pointing at `obsidian://open?vault=<vault>&file=_epi%2Fraw%2F<slug>%2Fpaper.pdf` (path `_epi/raw/<slug>/paper.pdf`, no `papers/` segment). The legacy wikilink form `"[[_epi/raw/<slug>/paper.pdf|<slug>]]"` remains accepted for EPI-generated pages. `concepts/, derivations/, experiments/, synthesis/, reports/, and opportunities/` use one or more clickable original-paper PDF links for the papers the page materially uses. Plain path text, the alias `原论文 PDF`, and metadata/MinerU/DOI/arXiv entries do not satisfy the contract; put those in the page body.

`tags` uses five facets in order — `domain/`, `method/` (one or more), `task/`, `topic/` (optional), and a required `evidence/` tier. `provenance` is three qualitative bullet lists (`extracted`, `inferred`, `ambiguous`), not numeric ratios, mirrored by a body `## Provenance` block with stance labels. The full references contract is `../skills/paper-research-wiki/references/references-page-anatomy.md`.

Initial lifecycle is `draft` or `review-needed`. Do not mark pages `verified` until source reread, formula review, figure/table review, lint, and human review have passed.
