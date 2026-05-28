# Evaluation

EPI uses Plugin Eval as a development and release quality layer. Plugin Eval does not replace the runtime paper critics.

Local Plugin Eval root:

`C:\Users\liuchf\.codex\plugins\cache\openai-curated\plugin-eval`

Current local CLI path:

`C:\Users\liuchf\.codex\plugins\cache\openai-curated\plugin-eval\603a6e80\scripts\plugin-eval.js`

Development loop:

```text
develop or modify EPI
  -> Plugin Eval analyze
  -> EPI custom metric pack
  -> benchmark typical tasks
  -> compare before/after
  -> generate improvement brief
  -> skill-aware-evolve proposal
  -> human review and validation
  -> activate approved asset changes
```

Run static analysis:

```powershell
node C:\Users\liuchf\.codex\plugins\cache\openai-curated\plugin-eval\603a6e80\scripts\plugin-eval.js analyze D:\paper-search\plugins\epi --format markdown
```

Run with the EPI metric pack:

```powershell
node C:\Users\liuchf\.codex\plugins\cache\openai-curated\plugin-eval\603a6e80\scripts\plugin-eval.js analyze D:\paper-search\plugins\epi --metric-pack D:\paper-search\plugins\epi\metric-packs\epi-quality-gates\manifest.json --format markdown
```

The markdown report is useful for the built-in Plugin Eval summary. To verify the custom EPI checks directly, use JSON output or run the emitter:

```powershell
node C:\Users\liuchf\.codex\plugins\cache\openai-curated\plugin-eval\603a6e80\scripts\plugin-eval.js analyze D:\paper-search\plugins\epi --metric-pack D:\paper-search\plugins\epi\metric-packs\epi-quality-gates\manifest.json --format json --output D:\codex-tmp\epi-plugin-eval.json
$payload = Get-Content -Raw D:\codex-tmp\epi-plugin-eval.json | ConvertFrom-Json
$payload.extensions[0].checks | Select-Object id,status
```

```powershell
node D:\paper-search\plugins\epi\metric-packs\epi-quality-gates\emit-epi-quality-gates.js D:\paper-search\plugins\epi plugin
```

The EPI metric pack checks:

- `run-state.json` contract exists.
- Critic gate is represented before compiled wiki promotion.
- `No critic pass, no compiled wiki write` is explicit.
- Raw `paper.pdf` and `metadata.json` retention is explicit.

Generated `.plugin-eval/` run artifacts are local development outputs and should stay out of commits unless the user explicitly asks to publish a benchmark report.
