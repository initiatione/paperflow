# Extract Papers

Use this when the user asks to extract, process, or deposit EPI-collected papers.

1. Resolve the target vault.
2. Locate `_epi/staging/papers/*/wiki_deposition_task.json`.
3. Run a preflight check and group papers as ready, needs human approval, blocked, or already recorded.
4. For ready papers, read source bundle artifacts before writing.
5. Write staged or formal pages according to the target vault contract.
6. Preserve source support status and evidence addresses.
7. Write or update `final-source-review.json`.
8. Tell the user which EPI `record-wiki-ingest` command remains.

Stop when source artifacts are missing and point back to EPI `paper-gate`.
