# EPI Evaluation

Release checks:

```powershell
python -m pytest tests\epi -q
python -m pytest plugins\epi -q
python -m coverage run -m pytest tests\epi
python -m coverage xml -o plugins\epi\coverage\coverage.xml
node <plugin-eval.js> analyze <plugin-root> --format markdown
```

`tests\epi` is the source behavioral suite. `tests\epi\test_wrapper_entrypoints.py` covers marketplace-visible wrappers for `scripts\orchestrator.py`, `scripts\init_paper_wiki.py`, and the MinerU skill wrapper.

Current Windows Plugin Eval builds absolute paths with backslashes, while its Python test-file heuristic matches only `/tests/` or `/test_*.py`, so `py-tests-missing` can appear even when `python -m pytest plugins\epi -q` passes. Treat that warning as an evaluator path-normalization limitation unless Plugin Eval starts reporting `py_test_file_count > 0`.

`deferred_cost_tokens-budget-high` is expected while `docs\epi-linkage.md` remains inside the plugin package as the required Chinese chain contract. Do not remove that document only to raise the static score. Valid budget cleanup is limited to deleting generated/redundant package files, trimming duplicated prose, and keeping `docs\workflow.md`, `docs\evaluation.md`, and `docs\config.md` as compact entrypoints.

Keep `.plugin-eval`, `.pytest_tmp*`, `.coverage`, and generated coverage artifacts out of commits. If the release coverage XML is intentionally refreshed, it must be force-added because `coverage/` is ignored.
