# EPI Evaluation

Recommended local checks:

```powershell
python -m pytest tests\epi -q
python -m coverage run -m pytest tests\epi
python -m coverage xml -o plugins\epi\coverage\coverage.xml
node C:\Users\liuchf\.codex\plugins\cache\openai-curated\plugin-eval\719ed655\scripts\plugin-eval.js analyze D:\paper-search\plugins\epi --format markdown
```

Generated `.plugin-eval`, `.pytest_tmp*`, `.coverage`, and `coverage` artifacts stay out of commits.
