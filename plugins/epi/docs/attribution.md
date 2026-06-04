# EPI Attribution

Discovery wraps an external `paper-search` command and records command, source, query, and raw-response provenance in each run. `prepare-ranked` is the narrow search -> acquire -> MinerU parse path for raw preparation only. MinerU parsing is optional and uses the local `skills\mineru-paper-parser\scripts\mineru_batch_to_md.py` entrypoint; successful runs keep final parse artifacts under `mineru/` and only lightweight command logs under `mineru-command/`.

MinerU parsing is an internal helper capability for EPI, not a separate marketplace plugin.

EasyScholar quality enrichment ports the API integration pattern from `chaosman42/easyscholar-mcp`, an MIT License project, into EPI's native Python discovery pipeline. EPI reuses the EasyScholar publication-rank endpoint semantics and `EASYSCHOLAR_SECRET_KEY` environment convention, but does not embed the upstream Node MCP server. The enrichment writes `easyscholar-record.json` and candidate `verified_metrics.easyscholar` evidence when available; missing keys or API failures are soft failures and reported as `未核实`.

EPI keeps raw artifacts under `_epi/raw` and evidence handoff bundles under `_epi/staging`. Final Obsidian/LLM Wiki pages are written by the wiki ingest agent according to the target vault contract; the formal EPI page families are `references/`, `concepts/`, `derivations/`, `experiments/`, `synthesis/`, `reports/`, and `opportunities/`. EPI can hand off evidence for these families, but it does not decide final page authority.
