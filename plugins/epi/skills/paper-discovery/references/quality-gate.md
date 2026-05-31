# Quality Gate

Apply a quality gate before recommendation: a paper should usually have strong profile/topic fit, a real contribution, credible validation, DOI or stable arXiv ID, available PDF, and at least one quality signal such as reputable configured venue, citations, code/data, field evidence, replication, strong benchmark, or recent journal acceptance.

Venue prior from `venue-prior.md` can raise or lower reading priority, but it cannot pass the quality gate by itself. A paper with weak topic fit, unclear identity, no PDF, or unverifiable claims should not become Tier A only because the venue is famous.

Two-stage retrieval changes when the gate runs: do not reject too early during the high-recall pool stage unless the item is clearly off-topic, duplicated, or explicitly excluded. Apply strict Tier A/B/C/Reject labels only after deduplication, source verification, and citation/venue checks.

Separate quality tiers:

- Tier A: configured top venue or strong field venue, DOI, PDF, high topic fit, and strong validation such as field study, replication, safety proof, clinical/engineering/data evidence where appropriate, or convincing benchmark.
- Tier B: good journal/conference or arXiv with strong method fit and credible experiments, but missing one important signal such as code, citations, or field validation.
- Tier C: relevant but weaker evidence, generic method work not tied to the user's profile, low metadata confidence, old work, or preprint-only. Include only if it meaningfully broadens the map.
- Reject: reviews/surveys when excluded, generic papers not tied to the configured domain/task, no PDF, unclear bibliographic identity, or papers whose claims cannot be verified.

For narrow domains, field-specific validation from the user's config can outweigh a generic top venue paper that only touches the topic superficially.

If the EPI `rank.json` misses obviously high-quality papers found by live verification, report that as a recall gap under `EPI 实测证据` and run a sharper query before finalizing when time allows.
