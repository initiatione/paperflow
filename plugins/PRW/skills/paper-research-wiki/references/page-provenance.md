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
  Evidence: MinerU Markdown 第 X 节; MinerU TeX Table I; 原论文 PDF (source: <obsidian:// link>).
- Inference: <cross-page conclusion>
  Support: inferred
  Basis: <reasoning / which pages it rests on>
```

For `references/ pages`, frontmatter `sources` must contain exactly one clickable original-paper PDF link. Canonical form: a Markdown link displayed with the paper title pointing at `obsidian://open?vault=<vault>&file=_epi%2Fraw%2F<slug>%2Fpaper.pdf` (path `_epi/raw/<slug>/paper.pdf`, no `papers/` segment); the legacy `"[[_epi/raw/<slug>/paper.pdf|<slug>]]"` wikilink form remains accepted for EPI-generated pages. Do not use plain path text, the alias `原论文 PDF`, or metadata/MinerU/DOI/arXiv entries in frontmatter `sources`.

Relink, tag, alias, and merge repairs must keep support labels visible in final pages.

When links express semantic relationships, write a `relationships:` frontmatter block with `target` and `type`. Allowed types follow the upstream pattern: `extends`, `implements`, `contradicts`, `derived_from`, `uses`, `replaces`, and `related_to`.
