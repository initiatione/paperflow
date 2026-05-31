# EPI Workflow

Use `doctor --json` when install, dependency, or vault state is unclear.

中文主链路和维护契约见 `docs\epi-linkage.md`。每次修改或优化 EPI 插件，都必须检查并同步更新该文档。

本机依赖由 `%USERPROFILE%\.codex\plugins\paper-search\epi\runtime.json` 自动加载：优先 paper-search MCP server，CLI 作为 fallback，MinerU token 从环境或 `mineru.env` 读取。不要把 token 写入 runtime.json，也不要在报告里打印 token 值。

EPI 是通用论文插件，不默认任何学科方向。`dry-run` 会从 `<vault>\_meta\epi-config.yaml` 的 profile、domains、positive/negative keywords、venue prior 和当前请求生成 `query-plan.json`，再按 query variants 调用 MCP/CLI 搜索、去重、过滤和排序。Query plan 的扩展词用于扩大召回；ranking 的画像匹配词只来自用户 config 和当前请求核心词，避免宽召回词稀释窄主题相关性。AUV、机器人、医学等只能来自用户配置、当前请求或显式领域 hint。

```powershell
python scripts\orchestrator.py dry-run --query "<your topic>" --max-results 20 --vault <vault>
python scripts\orchestrator.py dry-run --query "<your topic>" --max-results 20 --vault <vault> --json
python scripts\orchestrator.py prepare-ranked --run-id <run-id> --max-papers 10 --skip-existing --vault <vault>
python scripts\orchestrator.py prepare-ranked --run-id <run-id> --max-papers 10 --skip-existing --vault <vault> --json
python scripts\orchestrator.py advance-ranked --run-id <run-id> --max-papers 3 --vault <vault>
python scripts\orchestrator.py research-queue --vault <vault>
python scripts\orchestrator.py paper-gate --slug <paper-slug> --vault <vault>
python scripts\orchestrator.py wiki-ingest-handoff --slug <paper-slug> --vault <vault>
```

Dry-run writes only `_runs`; `--json` prints the run id and key artifact paths for agent/tool chaining. `prepare-ranked` is the precise search -> acquire -> MinerU raw-parse path and stops before reader/critic/staging; use `--max-papers 10 --skip-existing` for real batches and `--max-papers 1` only for smoke tests. `prepare-ranked --json` prints the prepared run id, source run id, processed/skipped counts, stop point, and key report paths for automation. Full ingest writes raw artifacts, then staging writes `_staging` only after critic pass. EPI prepares evidence drafts, a lightweight report, and `wiki-ingest-brief.json`; final Obsidian/LLM Wiki pages are written by the wiki ingest agent according to the target vault contract.

Reader v2 creates role notes plus `reader/evidence-map.json`:

- `nature-sci-editor`: novelty, audience, caveat.
- `peer-reviewer`: method, benchmark, reproducibility.
- `senior-domain-researcher`: theory insight, experiment ideas, domain fit.

Critic quorum combines paper, parse, reader, editorial, peer-review, and domain-fit gates. Hard failures set `outcome=revise-reader`; warnings become caveats. Staging prepares evidence drafts plus `reports/<slug>-reading-report.md` as the low-burden entrypoint.

```powershell
python scripts\orchestrator.py research-queue --bucket needs_reader_repair --vault <vault>
python scripts\orchestrator.py research-queue --bucket reproducibility_caveats --actions --json --vault <vault>
```

Queue buckets: `ready_to_promote`, `needs_reader_repair`, `warning_only`, `reproducibility_caveats`. `ready_to_promote --actions` must inspect current `paper-gate`; for current agent-mediated plans it suggests `run-wiki-ingest-agent` with a `wiki-ingest-handoff` command only when the remaining action is `human-approval`. Legacy compiled-draft plans may still expose `promote-to-wiki`.

Suggested draft routes may use `references/`, `concepts/`, `synthesis/`, and `reports/`, but they are non-authoritative. The target vault `AGENTS.md` and `_meta/*` decide final page paths, frontmatter, tags, links, merge policy, and staged writes. `wiki-ingest-brief.json` includes `wiki_rule_source_model`: resolve user instruction, target vault contract, personalized `liuchf/wiki-skills`, Ar9av/obsidian-wiki, kepano/obsidian-skills, then local `llm-wiki` / `wiki-ingest` / `obsidian-markdown` helper skills. The brief also carries a source-first policy: final wiki ingest must re-read `mineru/paper.md`, `mineru/paper.tex`, `mineru/images/*`, and `mineru/mineru-manifest.json`; reader and critic outputs are supporting evidence, not substitutes for the source paper. `wiki-ingest-handoff` is read-only: it renders the current paper gate, contract-file presence, rule source priority, suggested routes, and the agent checklist for the wiki ingest step. Reading reports stay lighter than full reader output: quick take, 5-minute path, role notes, theory/experiment ideas, evidence map, suggested wiki routes, quality gate status, and compact reproducibility caveats.
