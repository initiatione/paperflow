---
name: paper-discovery
description: "Use when running EPI paper search/ranking dry-runs, finding high-quality papers for a topic, excluding reviews/surveys on request, or starting the precise EPI steps 1-3 path: search, ranked selection, download, and MinerU parse without reader/critic/staging."
---

# Academic Paper Discovery

Use this skill for search/rank dry-runs and the narrow steps 1-3 path. Keep the main file thin and load the references below for the actual policy:

- `README.md`
- `references/query-planner.md`
- `references/domain-ontology.md`
- `references/search-protocol.md`
- `references/source-tiers.md`
- `references/dedup-engine.md`
- `references/venue-prior.md`
- `references/two-stage-retrieval.md`
- `references/citation-graph.md`
- `references/evaluation-set.md`
- `references/workflows/multi-source-discovery.md`
- `references/quality-gate.md`
- `references/output-format.md`

The full EPI chain stays documented in `docs\epi-linkage.md`. If setup is unclear, run `doctor` or `config-status`. If config is missing, stop discovery and use `config-setup`; config onboarding lives in `docs\config.md` 的 `## 聊天式初始化脚本`，不要自由发挥成技术字段问卷，不要一次性输出完整默认配置.

```powershell
python scripts\orchestrator.py doctor --plugin-root <plugin-root> --vault <vault> --json
python skills\paper-discovery\scripts\query-planner.py --topic "<topic>" --domain auto --max-queries 8
python skills\paper-discovery\scripts\query-planner.py --topic "<review topic>" --domain auto --include-reviews --max-queries 8
python scripts\orchestrator.py dry-run --query "<topic>" --max-results 10 --sources arxiv,semantic,openalex,crossref --plugin-root <plugin-root> --vault <vault>
python scripts\orchestrator.py dry-run --query "<exact narrow topic>" --no-query-plan --max-results 10 --sources arxiv,semantic,openalex,crossref --plugin-root <plugin-root> --vault <vault>
python scripts\orchestrator.py prepare-ranked --run-id <run-id> --max-papers 10 --skip-existing --include-review-candidates --vault <vault>
python scripts\orchestrator.py prepare-ranked --run-id <run-id> --max-papers 1 --vault <vault>
```

Default `dry-run` writes `query-plan.json`, derives query variants from the user's EPI config/profile plus the request topic, and excludes review/survey/meta candidates before dedup/filter/rank. EPI is field-agnostic: do not hardcode AUV, robotics, AI, medicine, or any other discipline unless those terms are present in the user's config or the current request. If the user explicitly asks for reviews or surveys, keep that intent and do not force non-review exclusions. Use `--no-query-plan` only when debugging or when the profile-derived plan clearly broadens away from the user's exact topic.

`prepare-ranked` downloads selected ranked papers and parses them with MinerU, then stops after `_raw\papers\<slug>\mineru\...`. For real testing, use `--max-papers 10 --skip-existing`; `--max-papers 1` is a smoke test only. `review-candidate` means "lower ranking confidence", not necessarily review/survey. Include it when the user asks to process all found papers or when a narrow domain run marks relevant papers conservatively. Verify evidence with `search-record.json`, `acquire-record.json`, `parse-record.json`, `paper.pdf`, `mineru\paper.md`, `mineru\paper.tex`, `mineru\images`, and `mineru\mineru-manifest.json`.

Safety: `dry-run` writes only `_runs/<run-id>/`. `prepare-ranked` writes raw paper artifacts only and stops after parse.
