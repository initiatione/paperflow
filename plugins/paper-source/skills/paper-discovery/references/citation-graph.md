# Citation Graph Expansion

Use citation graph expansion after an initial candidate pool finds 2-5 strong seed papers. This borrows the `related articles` idea from academic search systems but adapts it to robotics/control.

## When To Use

- The user asks for `latest`, `high quality`, `must not miss good papers`, or `not review`.
- A strong paper is found but the first result set lacks journal/conference versions.
- arXiv results look promising but peer-reviewed versions may exist.
- The topic has obvious venue families missing from the candidate pool.

## Expansion Steps

1. Pick seed papers with stable DOI/arXiv ID and high topic fit.
2. Query Semantic Scholar/OpenAlex-style metadata for:
   - cited-by papers from the last 3 years
   - references that look like foundational methods
   - related papers when the source supports it
3. Search title snippets to find journal/conference versions of arXiv preprints.
4. Merge expanded candidates back into the Stage 1 pool.
5. Deduplicate and quality-gate normally.

## Guardrails

- Do not let citation graph expansion drift into generic RL or generic robotics.
- Prefer recent cited-by papers for `latest` requests.
- Prefer foundational references only when they explain why a new paper matters.
- Mark expansion evidence in the final `EPI 实测证据`.
