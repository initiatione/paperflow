# Page Provenance

Support labels:

- `source-grounded`
- `metadata-only`
- `inferred`
- `unsupported`

Every durable claim needs an evidence address. Formula and figure claims need formula or figure evidence. Unsupported claims stay out of main factual prose.

Relink, tag, alias, and merge repairs must keep support labels visible in final pages.

When links express semantic relationships, write a `relationships:` frontmatter block with `target` and `type`. Allowed types follow the upstream pattern: `extends`, `implements`, `contradicts`, `derived_from`, `uses`, `replaces`, and `related_to`.
