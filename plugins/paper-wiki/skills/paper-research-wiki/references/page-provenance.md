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
  Evidence: MinerU Markdown 第 X 节; formula-index.json/Table I; 原论文 PDF (source: <obsidian:// link>).
- Inference: <cross-page conclusion>
  Support: inferred
  Basis: <reasoning / which pages it rests on>
```

For `references/ pages`, frontmatter `sources` must contain exactly one short source label. Do not put Markdown links, `[[...]]` wikilinks, `_paper_source/`, legacy `_epi/`, PDF paths, DOI/arXiv URLs, metadata paths, MinerU paths, or figure paths in frontmatter `sources`. Do not write `[[...]]` wikilinks to `_paper_source/` from frontmatter or formal-page body links. Frontmatter `sources:` must stay scan-friendly; frontmatter `sources:` must stay scan-friendly. Put the full clickable PDF URI in `## 原文与证据入口` as a Markdown link displayed as `原论文 PDF`, pointing at `obsidian://open?vault=<vault>&file=_paper_source%2Fraw%2F<slug>%2Fpaper.pdf` (path `_paper_source/raw/<slug>/paper.pdf`, no `papers/` segment); put the full clickable PDF URI in `## 原文与证据入口`, not in properties. Old artifacts may be read for compatibility, but recorded formal pages must use short `sources` labels plus the body PDF URI before `record-wiki-ingest`.

Relink, tag, alias, and merge repairs must keep support labels visible in final pages.

When links express semantic relationships, write a `relationships:` frontmatter block with `target` and `type`. Allowed types follow the upstream pattern: `extends`, `implements`, `contradicts`, `derived_from`, `uses`, `replaces`, and `related_to`.

Formal-page `[[wikilink]]` targets, including `relationships:` targets and page-end `## Related`, may point only to `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/`. Internal evidence paths under `_paper_source/`, legacy `_epi/`, snapshots, and staging directories may appear as `obsidian://` URI links, `file:///` image addresses, or code/plain text paths only.
