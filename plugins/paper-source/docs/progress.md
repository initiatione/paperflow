# Paper Source 插件进度说明

更新时间：2026-06-15。文档权威分工（doc map）见 `docs/paper-source-linkage.md` 顶部；本文档只记录当前源码树的状态快照、已知风险和下一步计划。逐轮变更历史见 `docs/CHANGELOG.md`。

## 当前定位

Paper Source 当前聚焦“按用户画像/config 衍生的高质量论文收集和整理 -> Obsidian/LLM Wiki 知识沉淀 -> 轻阅读负担报告”。它是通用学术论文插件，不默认任何学科方向；AUV、机器人、AI、医学等词只能来自用户配置、当前请求、Research Brief 或 agent 显式传入的 query variants / domain focus terms。

当前 `plugin.json` 中的版本：Paper Source `2.2.0`，Paper Wiki `1.0.0`。本轮 Paper Source 是 minor bump：新增高层 `discover-papers` 命令和 `discover_papers.py` 编排模块，把自然语言发现默认串成 dry-run evidence + `paper_source.auto_staging`，记录 `discover-papers-record.json`，默认保留 review/survey/meta-analysis，只有明确 non-review intent 才排除，并继续停在 approval / wiki trigger / wiki-ingest record / Paper Wiki 正式页之前。上轮 Paper Source `2.1.1` 是 patch bump：新增 `auto_staging.py` / `paper-source-auto-staging-plan-v1`，基于 `report.json.session_recommendations` 选择最多 3 篇 PDF-available 主推荐进入 fast source-staging，review/survey/meta-analysis 默认最多 1 个 slot，`needs_pdf` 保留 manual-download links 但不 staging，并刷新 `auto_staging_status`。Paper Source `2.1.0` 是 recommendation output minor bump：在 `report.json` 中新增 `session_recommendations` / `paper-source-session-recommendations-v1` 作为 chat/session 推荐输出合同；主推荐列表默认最多 10 篇，排除 `review-candidate`，Tier C / review 候选进入 appendix，rejected 只做 count/reason 摘要，中文摘要由调用 agent 基于 original abstract evidence 生成。Paper Source `2.0.0` 是 slim-down breaking bump；Paper Source `1.1.0` 是 discovery minor bump，默认 discovery 轻量化，先用 wiki `_meta/reference-index.json` 去重并输出 `already_in_wiki:<page>`，再 fallback 到 raw library；同时新增 `discover-to-handoff`、`discovery-diagnostics.json`、selection policies，以及 hard/soft query-plan provenance。历史 source manifest 曾从 Paper Source `0.1.12` / Paper Wiki `0.1.5` 到 Paper Source `0.1.13` / Paper Wiki `0.1.6`，再到 Paper Source `0.1.14` / Paper Wiki `0.1.7`、Paper Source `0.2.1`、`0.2.2`、`0.2.3`、Paper Source `0.2.4` / Paper Wiki `0.2.3`、Paper Source `0.2.5` / Paper Wiki `0.2.4`、Paper Source `0.2.6` / Paper Wiki `1.0.0`、Paper Source `1.0.0`、`1.0.1`、`1.0.2`、`1.0.3`、`1.0.4`、`1.0.5`、`1.0.6` / Paper Wiki `1.0.0`；installed cache 曾见 Paper Source `1.1.0`、`0.1.11`、`0.1.10`、`0.1.8` 和 source `0.2.0`，因此 runtime claims 必须区分 source checkout、installed cache 和当前 Codex session。

## 能力快照

- 配置与安装：`config-setup`、`doctor --json`、`runtime.json`、provider readiness、`MINERU_TOKEN` set/missing 报告、paper-search MCP/CLI fallback、adaptive Python detection 和 `import paper_search_mcp` 探测。
- 论文发现：`discover-papers` 自然语言默认入口、用户画像/config 驱动的 query planner、agent-supplied `--query-variant` / `--domain-focus-term` / `--agent-query-plan-json`、wiki `_meta/reference-index.json` first dedupe、hard/soft query-plan provenance、request constraints (`--year-min`, `--code-policy`)、selection policies、`discovery-diagnostics.json`、`venue prior`、`domain ontology`、`two-stage retrieval`、`citation graph`、`evaluation set`、source routing、source coverage、EasyScholar default-on、review/survey 默认保留、`session_recommendations`、`auto_staging_plan` 和 `未核实` 指标。
- 论文推进：默认 discovery 只给候选和 wiki 去重；`discover-to-handoff` / `prepare-ranked --max-papers 10 --skip-existing` 是显式 source-staging 深入路径，包含 manual download card、identity check、MinerU Markdown/images、非空原生 TeX（若存在）、`mineru/mineru-manifest.json`、`MinerU reported done but produced no Markdown output` 明确错误。
- 读者与审查：reader/claim-support、`paper-quality-critic`、`parse-quality-critic`、critic quorum、source bundle audit 和 `paper-gate`。
- Wiki handoff：`wiki-ingest-handoff`、`record-human-approval`、`wiki-ingest-trigger`、`record-wiki-ingest`、`wiki_ingest_recorded`、`waiting_for_human_gate`、`ready_for_agent=false`、`ready_after_human_approval=true`。
- Wiki ask：Paper Source `wiki-ask` 是 read-only formal graph / 程序化 fallback；Paper Wiki `ask_wiki` 是对话主入口。
- 生命周期：bounded lifecycle cleanup 使用 `retention.json`、默认 3000 files / 1 GiB、`over_budget=false` 视图、`run-lifecycle`、`raw-cleanup`、repository-maintenance、migrations、`wiki-reset`、formal-page-snapshots、tmp-manual-pdfs；preview 不刷新 `_paper_source/manifest.json`，不得删除 `_paper_source/raw`。
- 质量环：`Plugin Eval`、`paper-source-quality-gates`、benchmark、`evaluation-brief`、`paper-source-improvement-brief-v1`、`source_completeness` 和 `quality_loop_sources_complete`。

## 最近验证

最近可复用的验证信号：

```powershell
python -m pytest tests\paper_source\test_cli_parser.py tests\paper_source\test_normalize_filter_rank.py tests\paper_source\test_orchestrator_dry_run.py tests\paper_source\test_current_docs.py -q --basetemp .pytest_tmp_agent_query_plan_docs  # 118 passed
python -m pytest tests\paper_source\test_cli_parser.py tests\paper_source\test_paper_discovery_query_planner.py tests\paper_source\test_orchestrator_dry_run.py tests\paper_source\test_batch_advance_router.py -q  # 105 passed
python -m pytest tests\paper_source -q  # 599 passed
python -m pytest tests\paper_research_wiki\test_plugin_contract.py tests\paper_source\test_skill_bundle_contract.py tests\test_marketplace_manifest.py -q  # 86 passed
python -m json.tool plugins\paper-source\.codex-plugin\plugin.json > $null
python -m json.tool plugins\paper-wiki\.codex-plugin\plugin.json > $null
git diff --check  # passed; CRLF conversion warnings only
python <plugin-creator>\scripts\validate_plugin.py plugins\paper-source  # passed
codex plugin marketplace remove paperflow --json
codex plugin marketplace add <repo-root> --json
codex plugin add paper-source@paperflow --json  # installed Paper Source 1.1.0 from local marketplace
python -m pytest tests\paper_source\test_wiki_query.py tests\paper_source\test_cli_parser.py tests\paper_research_wiki\test_plugin_contract.py tests\paper_source\test_current_docs.py -q
python -m pytest tests\paper_research_wiki\test_plugin_contract.py tests\paper_source\test_skill_bundle_contract.py tests\test_marketplace_manifest.py -q
python -m pytest tests\paper_source -q
python -m coverage run -m pytest tests\paper_source -q
python -m coverage xml -o plugins\paper-source\coverage\coverage.xml
node <plugin-eval.js> analyze <plugin-root> --format markdown
git diff --check
```

Historical focused results preserved for comparison: `107 passed in 1.35s`、`55 passed in 0.42s`、`70 passed in 1.16s`、`287 passed in 30.16s`、`45 passed in 10.19s`。质量门历史信号：pass rate `1`，Plugin Eval `82/100`。Source coverage / read-preview full run historically reached `391 passed in 53.81s`; current release must rerun rather than inherit that snapshot.

S3a 文档/契约 canonical 化已完成并归档。当前实现队列是 S3b brief-first machine-contract：`wiki-ingest-brief.json` is the only new Paper Source-to-Paper Wiki handoff，`wiki_deposition_task.json` 只作为历史 handoff 清理对象，用户黄金路径收敛到 Paper Wiki `$paper-research-wiki`，external wiki skills are optional helpers / policy references。

- Paper Source/Paper Wiki boundary: `wiki-ingest-brief.json` is the canonical Paper Source-to-Paper Wiki handoff; `wiki_deposition_task.json` is historical cleanup only; Paper Wiki `$paper-research-wiki` is the formal paper wiki writing layer; `paper-source-paper-deposition` is a retired handoff cleanup entry; external wiki skills are optional helpers / policy references.

本轮 S3b 验收目标：`tests/paper_source/test_wiki_deposition_task.py`、`tests/paper_source/test_wiki_ingest_handoff.py`、`tests/paper_source/test_wiki_ingest_record.py`、`tests/paper_source/test_one_paper_ingest.py`、`tests/paper_source/test_paper_gate.py`、`tests/paper_research_wiki/test_plugin_contract.py`、`tests/paper_source/test_current_docs.py` 和 `tests/paper_source/test_skill_bundle_contract.py` 必须保持通过；再跑 JSON manifest 校验、stale wording grep 和 `git diff --check`。

## 发布前必须重跑

```powershell
python -m pytest tests\paper_source -q --basetemp .pytest_tmp_paper_source_current
python -m pytest tests\paper_research_wiki tests\paper_source\test_skill_bundle_contract.py tests\test_marketplace_manifest.py -q
python -m json.tool plugins\paper-source\.codex-plugin\plugin.json
python -m json.tool plugins\paper-wiki\.codex-plugin\plugin.json
python <plugin-creator-validate-script> <plugin-root>
python -m coverage run -m pytest tests\paper_source
python -m coverage xml -o plugins\paper-source\coverage\coverage.xml
node <plugin-eval.js> analyze <plugin-root> --format markdown
git diff --check
```

验收标准：

- 源码测试通过，Paper Source/Paper Wiki plugin validation 通过。
- Plugin Eval 无 fail，分数不低于 `70/100`。
- coverage artifact 可被 Plugin Eval 识别。
- Windows `py-tests-missing` warning 若出现，记录为评估器路径识别限制。

## 下一步计划

1. 完成 S3b brief-first machine-contract 的剩余 metadata/full verification：`wiki-ingest-brief.json` 已是 canonical Paper Source-to-Paper Wiki handoff，默认 staging 不再要求 `wiki_deposition_task.json`。
2. 继续 S3b metadata、manifest、stale wording grep、full verification 和 integration decision。
3. 当前源码已进入 Paper Source `2.2.0`；当前机器历史上已把 `paperflow` marketplace source 切到本地 `<repo-root>`，并安装 Paper Source `1.1.0` 到 installed cache。`2.2.0` 仍需 marketplace refresh/reinstall/installed-cache verification 后才可声称运行态已更新；若要让 Git marketplace 用户获得同版本，还需要 commit/push 后再从 Git source upgrade。
4. 从新 Codex thread 运行 `doctor --json`、`config-status --json`、dry-run fixture smoke 和 `research-queue` 验证安装体验；当前 thread 不会重新加载刚安装的 skill metadata。
5. 对目标 vault 补齐 `AGENTS.md` 和 `_meta/*.md`，再让 Paper Wiki 消费 `wiki-ingest-brief.json` 和 reading report。

## 已知风险

- `docs/paper-source-linkage.md`、`docs/structure.md`、`docs/progress.md` 会增加 Plugin Eval deferred token 估算，但这些是当前维护材料，不应为了静态分数移出插件 docs。
- `paper-search` CLI、MinerU、Zotero 都是外部能力。缺失时应 warning 和引导，不应让只读诊断失败。
- `MINERU_TOKEN` 不得写入文档、日志、报告或配置预览，只能显示 set/missing。
- 当前机器的 Paper Source installed cache 已刷新到 `1.1.0`；开发源已是 `<repo-root>/plugins/paper-source` 的 `2.2.0`，用户级 `runtime.json` 不随 cache 版本目录替换。`2.2.0` 仍需 marketplace refresh/reinstall/installed-cache verification；Git marketplace 仍需 commit/push 后再 upgrade 才能让其他安装源看到同一版本。
- 最终 Obsidian/LLM Wiki 写入依赖目标 vault contract。Paper Source 只能提供 handoff 和 suggested routes，不能把固定脚本当成最终沉淀机制。
