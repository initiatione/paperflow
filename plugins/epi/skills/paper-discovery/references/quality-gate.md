# Quality Gate

Apply a quality gate before recommendation: a paper should usually have strong topic fit, a real method contribution, credible validation, DOI or stable arXiv ID, available PDF, and at least one quality signal such as reputable venue, citations, code/data, real AUV/field experiment, sim-to-real, safety guarantee, strong benchmark, or recent journal acceptance.

Venue prior from `venue-prior.md` can raise or lower reading priority, but it cannot pass the quality gate by itself. A paper with weak topic fit, unclear identity, no PDF, or unverifiable claims should not become Tier A only because the venue is famous.

Separate quality tiers:

- Tier A: journal/top robotics venue, DOI, PDF, high topic fit, strong validation such as sea trial, real AUV, sim-to-real, safety proof, or convincing benchmark.
- Tier B: good journal/conference or arXiv with strong method fit and credible experiments, but missing one important signal such as code, citations, or field validation.
- Tier C: relevant but weaker evidence, generic robotics/RL, low metadata confidence, old work, or preprint-only. Include only if it meaningfully broadens the map.
- Reject: reviews/surveys when excluded, generic RL not tied to the domain/control task, no PDF, unclear bibliographic identity, or papers whose claims cannot be verified.

For AUV/control searches, field validation, ocean-current disturbance modeling, hardware-in-the-loop, real platform evidence, sim-to-real transfer, and safety constraints are strong engineering signals. These can outweigh a generic top AI/ML venue paper that only uses robotics as an example.

If the EPI `rank.json` misses obviously high-quality papers found by live verification, report that as a recall gap under `EPI 实测证据` and run a sharper query before finalizing when time allows.
