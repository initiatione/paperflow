# Page Provenance Reference

Use this reference to keep EPI-extracted knowledge traceable after it leaves `_raw` and `_staging`.

## Minimum Page-Level Provenance

Adapt field names to the target vault contract, but preserve these facts somewhere queryable:

- `paper_slug`, title, DOI/arXiv ID, year, venue, and final page path.
- Source artifact bundle: `paper.pdf`, `metadata.json`, MinerU Markdown, TeX, images, manifest.
- Evidence artifacts: `reader/evidence-map.json`, `reader/claim-support.json`, critic reports, reading report.
- Final review artifacts: `final-source-review.json`, `wiki-ingest-record.json`, human approval record.
- Support status summary: count of source-grounded, metadata-only, inferred, and unsupported claims.

## Claim Line Contract

Each important claim should preserve:

- Claim text.
- Support status.
- Evidence address or basis.
- Scope/caveat when the paper only reports a limited setting.
- Optional synthesis hook: method, task, benchmark, dataset, metric, limitation, or conflict.

Good:

```markdown
- The paper reports a 12% improvement on Benchmark X under Setting Y.
  Support: source-grounded; stance=author-claim
  Evidence: mineru/paper.md#results; reader/claim-support.json#claim-008; Table 3
  Caveat: source reports this for Setting Y only.
```

Bad:

```markdown
- Method A is better than Method B.
```

## Provenance Block

When inline evidence would make the page noisy, use a compact local block:

```markdown
## Provenance

- Source bundle: paper.pdf; metadata.json; mineru/paper.md; mineru/paper.tex; mineru/images; mineru/mineru-manifest.json
- Evidence maps: reader/evidence-map.json; reader/claim-support.json
- Final source review: final-source-review.json
- Support status: source-grounded=<n>; metadata-only=<n>; inferred=<n>; unsupported=0
```

The page still needs enough claim-level markers for a future reader to know which statement maps to which evidence.

## Round-Trip Retrieval Hooks

Add structured hooks so later wiki queries can synthesize across papers:

- Method family and named algorithm.
- Task/application setting.
- Dataset, benchmark, metric, and baseline.
- Main claim, limitation, and reproduction caveat.
- Related paper slugs and likely conflict/complement pairs.
- Whether a claim is source-grounded, author-claim, metadata-only, or inferred.

These hooks are for retrieval and synthesis, not decoration.

## Final-Source-Review Checklist

Before `record-wiki-ingest`, verify:

- Each final page is inside the vault and outside EPI internal folders.
- `reviewed_artifacts[]` covers the required source bundle and hashes match.
- Formula review, figure/image review, and PDF fallback review are present.
- `final_page_provenance[]` includes every final page, page hash, and `source_grounded=true`.
- Page-local provenance exists; it is not only stored in sidecar JSON.
- Inferred or hypothesis content is labeled and separated from source-grounded factual prose.
