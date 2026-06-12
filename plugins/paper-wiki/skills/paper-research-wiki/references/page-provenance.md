# Page Provenance

Support labels:

- `source-grounded`
- `metadata-only`
- `inferred`
- `unsupported`

Every durable claim needs an evidence address. Formula and figure claims need formula or figure evidence. Unsupported claims stay out of main factual prose.

Tag the stance of each load-bearing claim: `author-method-description`, `author-claim-from-simulation`, `author-claim-from-experiment`, `source-grounded`, `inferred`, or `ambiguous`. Mark inferred prose with `^[inferred]` and uncertain prose with `^[ambiguous]`.

Every reference page ends with a `## Provenance` block, one entry per load-bearing claim, formula, and result:

```
- Claim: <statement>
  Support: source-grounded; stance=author-claim-from-simulation
  Evidence: MinerU Markdown 第 X 节; formula-index.json/Table I; 原论文 PDF (source: [<paper title>](obsidian://...paper.pdf)).
- Inference: <cross-page conclusion>
  Support: inferred
  Basis: <reasoning / which pages it rests on>
```

For `references/ pages`, frontmatter `sources` must contain exactly one Markdown link to the canonical source PDF, displayed as the source paper title: `[<paper title>](obsidian://open?vault=<vault>&file=_paper_source%2Fraw%2F<slug>%2Fpaper.pdf)`. Use `_paper_source/raw/<slug>/paper.pdf`, with no `papers/` segment. Non-reference families may contain one or more title-display source PDF links for materially used papers. Do not use `[[...]]` wikilinks, legacy `_epi` links, plain/relative PDF paths, DOI/arXiv URLs, GitHub URLs, metadata paths, MinerU paths, or figure paths in frontmatter `sources`. Do not write `[[...]]` wikilinks to `_paper_source/` from frontmatter or formal-page body links. In `## 原文与证据入口`, include the same canonical PDF URI as a Markdown link and use the paper title as the clickable text, not `原论文 PDF`. Old artifacts may be read for compatibility, but recorded formal pages must use canonical `_paper_source` title-display PDF links before `record-wiki-ingest`.

Relink, tag, alias, and merge repairs must keep support labels visible in final pages.

When links express semantic relationships, write a `relationships:` frontmatter block with `target` and `type`. Allowed types follow the upstream pattern: `extends`, `implements`, `contradicts`, `derived_from`, `uses`, `replaces`, and `related_to`.

Formal-page `[[wikilink]]` targets, including `relationships:` targets and page-end `## Related`, may point only to `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/`. Internal evidence paths under `_paper_source/`, legacy `_epi/`, snapshots, and staging directories may appear as `obsidian://` URI links, `file:///` image addresses, or code/plain text paths only.
