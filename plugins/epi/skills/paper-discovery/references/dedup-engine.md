# Dedup Engine

Deduplicate before ranking and before presenting recommendations. A high-quality search can run multiple query variants and sources; duplicate records must not inflate confidence.

## Identity Keys

Apply keys in this order:

1. DOI: lowercase, strip `https://doi.org/`, trim punctuation.
2. arXiv ID: normalize version suffix only for identity comparison; keep exact version in metadata if present.
3. Stable URL: DOI, arXiv, publisher, OpenReview, IEEE/ACM/Springer/ScienceDirect landing pages.
4. Normalized title: lowercase, remove punctuation, collapse whitespace, drop common stopwords.
5. Title + first author + year when DOI/arXiv is missing.

## Merge Preference

When duplicates appear, keep the record with:

1. DOI or stable arXiv ID.
2. Official publisher or venue metadata.
3. PDF URL and code URL.
4. Higher citation count with source noted.
5. More complete abstract and venue/year fields.

Do not silently discard useful fields from duplicates. Preserve alternate source names, source URLs, and metadata provenance when the implementation supports it.

## Wiki Library Dedup

Before recommending, compare candidates against `<vault>\_epi\\raw\\*\metadata.json`.

Reject already downloaded papers with:

```text
already_in_library:<slug>
```

Do not recommend them again unless the user explicitly asks to repair, reparse, or revisit an existing paper.

## Conflict Handling

- Same DOI but different title: keep DOI identity, mark metadata conflict for verification.
- Same title but different year/venue: prefer official DOI/publisher metadata and mark conflict.
- Preprint and published version: prefer published venue for ranking, keep arXiv as alternate source.
- Conference short paper and journal extension: treat as related but not automatically duplicate unless DOI/title/abstract strongly match.
