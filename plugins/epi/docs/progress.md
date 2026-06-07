# EPI 插件进度说明

更新时间：2026-06-07。文档权威分工（doc map）见 `docs/epi-linkage.md` 顶部；本文档只记录当前源码树的状态快照、已知风险和下一步计划。逐轮变更历史见 `docs/CHANGELOG.md`。

## 当前定位

EPI 当前聚焦“按用户画像/config 衍生的高质量论文收集和整理 -> Obsidian/LLM Wiki 知识沉淀 -> 轻阅读负担报告”。它是通用学术论文插件，不默认任何学科方向；AUV、机器人、AI、医学等词只能来自用户配置、当前请求或显式领域 hint。

当前 `plugin.json` 中的版本：EPI `0.2.1`，PRW `0.2.1`。历史 source manifest 曾从 EPI `0.1.12` / PRW `0.1.5` 到 EPI `0.1.13` / PRW `0.1.6`，再到 EPI `0.1.14` / PRW `0.1.7`；installed cache 曾见 EPI `0.1.11`、`0.1.10`、`0.1.8` 和 source `0.2.0`，因此 runtime claims 必须区分 source checkout、installed cache 和当前 Codex session。

## 能力快照

- 配置与安装：`config-setup`、`doctor --json`、`runtime.json`、provider readiness、`MINERU_TOKEN` set/missing 报告、paper-search MCP/CLI fallback、adaptive Python detection 和 `import paper_search_mcp` 探测。
- 论文发现：用户画像/config 驱动的 query planner、`venue prior`、`domain ontology`、`two-stage retrieval`、`citation graph`、`evaluation set`、source routing、source coverage、EasyScholar default-on 和 `未核实` 指标。
- 论文推进：`prepare-ranked --max-papers 10 --skip-existing`、manual download card、identity check、MinerU Markdown/TeX/images、`mineru/mineru-manifest.json`、`MinerU reported done but produced no Markdown output` 明确错误。
- 读者与审查：reader/claim-support、`paper-quality-critic`、`parse-quality-critic`、critic quorum、source bundle audit 和 `paper-gate`。
- Wiki handoff：`wiki-ingest-handoff`、`record-human-approval`、`wiki-ingest-trigger`、`record-wiki-ingest`、`wiki_ingest_recorded`、`waiting_for_human_gate`、`ready_for_agent=false`、`ready_after_human_approval=true`。
- Wiki ask：EPI `wiki-ask` 是 read-only formal graph / 程序化 fallback；PRW `ask_wiki` 是对话主入口。
- 生命周期：bounded lifecycle cleanup 使用 `retention.json`、默认 3000 files / 1 GiB、`over_budget=false` 视图、`run-lifecycle`、`raw-cleanup`、repository-maintenance、migrations、`wiki-reset`、formal-page-snapshots、tmp-manual-pdfs；preview 不刷新 `_epi/manifest.json`，不得删除 `_epi/raw`。
- 质量环：`Plugin Eval`、`epi-quality-gates`、benchmark、`evaluation-brief`、`epi-improvement-brief-v1`、`source_completeness` 和 `quality_loop_sources_complete`。

## 最近验证

最近可复用的验证信号：

```powershell
python -m pytest tests\epi\test_wiki_query.py tests\epi\test_cli_parser.py tests\paper_research_wiki\test_plugin_contract.py tests\epi\test_current_docs.py -q
python -m pytest tests\paper_research_wiki\test_plugin_contract.py plugins\epi\tests\test_skill_bundle_contract.py tests\test_marketplace_manifest.py -q
python -m pytest tests\epi -q
python -m coverage run -m pytest tests\epi -q
python -m coverage xml -o plugins\epi\coverage\coverage.xml
node <plugin-eval.js> analyze <plugin-root> --format markdown
git diff --check
```

Historical focused results preserved for comparison: `107 passed in 1.35s`、`55 passed in 0.42s`、`70 passed in 1.16s`、`287 passed in 30.16s`、`45 passed in 10.19s`。质量门历史信号：pass rate `1`，Plugin Eval `82/100`。Source coverage / read-preview full run historically reached `391 passed in 53.81s`; current release must rerun rather than inherit that snapshot.

本轮 S3a 验收目标：`tests/epi/test_current_docs.py`、`tests/paper_research_wiki/test_plugin_contract.py`、`tests/test_marketplace_manifest.py`、`tests/epi/test_runtime_config.py` 和 `plugins/epi/tests/test_skill_bundle_contract.py` 必须保持通过；再跑 JSON manifest 校验和 `git diff --check`。

## 发布前必须重跑

```powershell
python -m pytest tests\epi -q --basetemp .pytest_tmp_epi_current
python -m pytest tests\paper_research_wiki plugins\epi\tests tests\test_marketplace_manifest.py -q
python -m json.tool plugins\epi\.codex-plugin\plugin.json
python -m json.tool plugins\PRW\.codex-plugin\plugin.json
python <plugin-creator-validate-script> <plugin-root>
python -m coverage run -m pytest tests\epi
python -m coverage xml -o plugins\epi\coverage\coverage.xml
node <plugin-eval.js> analyze <plugin-root> --format markdown
git diff --check
```

验收标准：

- 源码测试通过，EPI/PRW plugin validation 通过。
- Plugin Eval 无 fail，分数不低于 `70/100`。
- coverage artifact 可被 Plugin Eval 识别。
- Windows `py-tests-missing` warning 若出现，记录为评估器路径识别限制。

## 下一步计划

1. 完成 S3a 文档/契约 canonical 化并验证。
2. 发布本轮修复 commit，并从 GitHub/marketplace 重新安装 EPI/PRW，确认 installed cache 版本变为 `0.2.1`。
3. 从新 Codex thread 运行 `doctor --json`、`config-status --json`、dry-run fixture smoke 和 `research-queue` 验证安装体验。
4. 对目标 vault 补齐 `AGENTS.md` 和 `_meta/*.md`，再让 PRW 消费 `wiki-ingest-brief.json` 和 reading report。

## 已知风险

- `docs/epi-linkage.md`、`docs/structure.md`、`docs/progress.md` 会增加 Plugin Eval deferred token 估算，但这些是当前维护材料，不应为了静态分数移出插件 docs。
- `paper-search` CLI、MinerU、Zotero 都是外部能力。缺失时应 warning 和引导，不应让只读诊断失败。
- `MINERU_TOKEN` 不得写入文档、日志、报告或配置预览，只能显示 set/missing。
- 当前安装 cache 不是开发源；源码提交并经 marketplace 升级后，安装副本才会变化。用户级 `runtime.json` 不随 cache 版本目录替换。
- 最终 Obsidian/LLM Wiki 写入依赖目标 vault contract。EPI 只能提供 handoff 和 suggested routes，不能把固定脚本当成最终沉淀机制。
