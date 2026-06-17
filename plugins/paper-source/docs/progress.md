# Paper Source 插件进度说明

更新时间：2026-06-18。文档权威分工（doc map）见 `docs/paper-source-linkage.md` 顶部；本文档只记录当前源码树的状态快照、已知风险和下一步计划。逐轮变更历史见 `docs/CHANGELOG.md`。

## 当前定位

Paper Source 当前聚焦“按用户画像/config 衍生的高质量论文收集和整理 -> Obsidian/LLM Wiki 知识沉淀 -> 轻阅读负担报告”。它是通用学术论文插件，不默认任何学科方向；AUV、机器人、AI、医学等词只能来自用户配置、当前请求、Research Brief 或 agent 显式传入的 query variants / domain focus terms。

当前 `plugin.json` 中的版本：Paper Source `2.3.11`，Paper Wiki `1.0.3`。本轮是 PS/PW 公共入口文案与 metadata 一致性 patch（详见 CHANGELOG 2.3.11）：把 `skills/wiki-setup/agents/openai.yaml` 的 awkward "an Paper Source paper wiki vault" 文案改为清晰语法，把 `stage_wiki_brief.py` 的 `provenance_policy` 改为 policy 措辞（"preserve provenance labels and maintain tag/alias taxonomy"），Paper Wiki `docs/structure.md` 区分 "no orchestrator-style user CLI" 与窄 helper wrapper 脚本；不删除任何 skill，discovery、source-staging、formal page、record 语义不变。上一轮 Paper Source `2.3.10` 是 script-size governance patch：新增 Python script 2000 行硬门禁，把 dry-run/search 编排拆到 `orchestrator_dry_run.py`，把 run lifecycle/shared helper 拆到 `orchestrator_common.py`，`orchestrator.py` 保持 CLI/workflow 兼容表面且降到 2000 行以内；ranking、query-planning、DOI、staging 和 Paper Wiki handoff 语义不变。Paper Source `2.3.9` 是 retired compiled-draft promotion action 的 active-surface 退役收尾与 `discover-to-handoff` 路由单一 owner 收敛 patch（详见 CHANGELOG 2.3.9）：`run_index.py` 与 `orchestrator.py` 不再为退役动作输出 readiness 或 recommended-action，`routing-rules.example.yaml` 删除 legacy stage 行，quality-gates metric pack 与其测试改用 critic-gate 证据；`discover-to-handoff` 只触发 `paper_ingest` 路由，不再与 `paper_discovery` 重复，新增 routing-contract 测试守卫单一 owner。Paper Source `2.3.8` 是 cross-discipline discovery quality-gate patch：`rank_candidates` 把 query-plan `priority_keywords` 作为严格 topic-fit 通道；当没有 hard anchors 时，普通 positive keyword topic fit 采用少量强命中即可饱和的 `positive_keywords_saturated` 规则，并把全量关键词覆盖率保留为 `keyword_coverage_score` 诊断，避免多学科长 profile 把明显相关论文稀释成 `weak_topic_fit`。`quality_gate.dimensions` 现在输出 identity、relevance、inspectability、validation、source_confidence、reproducibility 和 request_risk 七个通用维度，供所有学科解释质量门。文档同步明确 `openags/paper-search-mcp` 是 broad retrieval / metadata / dedupe / download / source coverage provider，不是 semantic quality gate 或 recommendation ranker；Paper Source 继续拥有 query planning、source routing、quality gate、DOI policy 和 chat-facing recommendation surfaces。Paper Source `2.3.7` 是 discovery quality-gate 与 recommendation status taxonomy patch：query-plan priority ranking 只把 hard domain anchors / domain focus terms 当作领域贴合优先分母，避免明确 AUV/underwater-vehicle 论文被 method/problem/context/profile 长词表稀释成 `weak_topic_fit`；`review_appendix` 现在只保留 DOI-present 且非 Reject 的待复核候选，`quality_tier=Reject` 进入 `quality_reject_debug`，保留 blocking reasons 与 query/source provenance；零主推荐 run 会在 `no_primary_recommendations_summary` 和 `report.md` 中解释是 DOI policy、quality gate、existing-library saturation 还是 recall gap 导致为空。Paper Source `2.3.6` 是 existing-library output-format 与 reference-index canonical dedupe patch：`paper-discovery` 的 `库中已有，可回看` 会话输出现在要求用一句简短说明加 Markdown 表格，列出论文、年份、状态、入口和 DOI，避免把已入库论文压成一行分号列表；`report.md` 的 `Already In Library Or Wiki` 也同步使用表格，并继续强调这些条目只是已在 wiki/raw library 的回看提醒，不是新推荐；`paper_library.py` 在 `_meta/reference-index.json` 加载成功时把它作为唯一 canonical backlog，跳过 raw metadata 扫描并记录 `raw_scan_policy`，只有 reference-index 缺失/不可用时才扫描 `_paper_source/raw/*/metadata.json` fallback。Paper Wiki `1.0.2` 是 reference-index refresh patch：写入、重写或 materially repair `references/` 页后，必须运行 `plugins/paper-wiki/scripts/refresh_reference_index.py --vault <vault> --json` 或等价命令刷新 `_meta/reference-index.json`，post-task check 必须验证改动页/source_id 已进入索引。Paper Source `2.3.5` 是 discovery recommendation DOI hardening patch：`normalize_candidates.py` 从 provider DOI、DOI URL、raw metadata 和 arXiv base id 派生 `10.48550/arXiv.<base_id>` 补齐 DOI，从 provider abstract/snippet 提取公开代码仓库 URL；dry-run 会对仍缺 DOI 的候选执行有上限的 targeted Grok/web DOI recovery，写 `doi-recovery-grok-*` artifacts 后重新 normalize；`session_recommendations.primary_recommendations` 和 `review_appendix` 现在只输出 DOI-present 论文，补不到 DOI 的候选记录在 `doi_recovery_summary`、`doi_resolution_summary` 和 `doi_filtered_summary` / `missing_required_doi`，不进入推荐或待复核清单，但会话层必须显示失败统计和候选清单，避免好论文静默丢失；skill docs 固定 `推荐优先看`、`新增待复核候选`、`库中已有，可回看` 三类输出边界，并要求 Grok 只有在真实 `ok`、有 records、无 fallback warning 时才算有效推荐证据。Paper Source `2.3.4` 是 Grok runtime resilience patch：`grok_search_adapter.py` 保留用户 `OPENAI_COMPATIBLE_MODEL` 首选项，在 `grok_provider_error` 或 `source_fallback` 时按 `PAPER_SOURCE_GROK_MODEL_FALLBACKS` / 默认 multi-agent 优先列表降级重试，并把非 secret 的 `model_attempts` 写入 `grok-search-raw.json`；`PAPER_SOURCE_GROK_PARALLEL_GRACE_SECONDS` 让 parallel fan-in grace 可配置，默认 180 秒。文档明确每个用户必须配置自己的 Grok/OpenAI-compatible endpoint/key/model，本机代理、TUN/fake-IP、DNS 或 Cloudflare challenge 症状属于 runtime 诊断，不进入插件默认或源码。Paper Source `2.3.3` 是 patch hardening：修复 live AUV 检索暴露的 discovery contract 回归，Grok supplemental search 使用 installed provider 支持的 `detailed` response format；ranking 给 query-plan hard anchors / task terms 一个 priority topic-fit 通道，避免窄题精确命中被长期 profile 稀释成 `weak_topic_fit`；`normalize_candidates` 保留 citation-count source provenance，paper-search adapter 不再把缺失 provider citation 字段伪装成已核实 0；`session_recommendations` 输出 DOI/primary URL、citation evidence、verified metrics、`verification_summary`、per-item verification warnings 和 `existing_library_appendix`。已入库 / 已在 wiki 的论文继续排除出新推荐和 auto-staging，只作为会话层分栏提醒。Paper Source `2.3.2` 是 patch bump：把可选 `grok-search-rs MCP` 纳入 Paper Source discovery skill workflow，而不是作为独立脚本入口。新增 `grok_search` vault config、`grok_search_mcp` runtime config、`--grok-mode targeted|parallel|off` / `--no-grok-search` CLI override、provider 分文件 artifact、paper-search-priority merge、Grok-only recommendation anchor gate，以及 `paper-discovery` workflow 文档。默认 targeted 会先跑 paper-search，结果足够好就跳过 Grok；parallel 是补短板并行搜，不缩短 paper-search 生命周期；无 paper-search usable candidate 时 Grok 只能写 evidence/diagnostics。本轮同时强化本机工具 runtime 配置边界：paper-search/Grok/MinerU/EasyScholar 工具接线是插件配置的一部分，`runtime_config.py` 记录 `path_policy`，`doctor --json` 报告 `runtime_path_policy`，并警告标准用户级 runtime 依赖开发 checkout、项目 `.env` helper、vault 内部、临时目录或版本化 plugin cache 的情况。Paper Source `2.3.1` 是 patch bump：MinerU ZIP 下载器新增 `PAPER_SOURCE_MINERU_CDN_RESOLVE` host/IP override，用于 MinerU 已 `done` 但 `full_zip_url` 因 fake-IP/TLS EOF 下载失败的环境；成功恢复会在 `mineru-manifest.json` 写 `download_recovery`，未配置时保持普通 DNS 行为。Paper Source `2.3.0` 是 minor bump：在既有 `human-approval.json` / `paper-source-human-approval-v1` 合同上新增显式 Codex automation approval handoff，`record-human-approval` 可选择记录 `codex-automation:<task-id>` actor、task/source/original authorization 等审计字段，并把 automation context 透传到 `wiki-agent-trigger.json`；普通 `discover-papers` / auto-staging 不推断 automation，仍停在 approval / wiki trigger / wiki-ingest record / Paper Wiki 正式页之前。Paper Source `2.2.1` 是 patch bump：同步 `paper-discovery/agents/openai.yaml`，让 UI-facing skill metadata 明确指向 `discover-papers` 自然语言默认入口。Paper Source `2.2.0` 是 minor bump：新增高层 `discover-papers` 命令和 `discover_papers.py` 编排模块，把自然语言发现默认串成 dry-run evidence + `paper_source.auto_staging`，记录 `discover-papers-record.json`，默认保留 review/survey/meta-analysis，只有明确 non-review intent 才排除，并继续停在 approval / wiki trigger / wiki-ingest record / Paper Wiki 正式页之前。Paper Source `2.1.1` 是 patch bump：新增 `auto_staging.py` / `paper-source-auto-staging-plan-v1`，基于 `report.json.session_recommendations` 选择最多 3 篇 PDF-available 主推荐进入 fast source-staging，review/survey/meta-analysis 默认最多 1 个 slot，`needs_pdf` 保留 manual-download links 但不 staging，并刷新 `auto_staging_status`。Paper Source `2.1.0` 是 recommendation output minor bump：在 `report.json` 中新增 `session_recommendations` / `paper-source-session-recommendations-v1` 作为 chat/session 推荐输出合同；主推荐列表默认最多 10 篇，排除 `review-candidate`，Tier C / review 候选进入 appendix，rejected 只做 count/reason 摘要，中文摘要由调用 agent 基于 original abstract evidence 生成。Paper Source `2.0.0` 是 slim-down breaking bump；Paper Source `1.1.0` 是 discovery minor bump，默认 discovery 轻量化，先用 wiki `_meta/reference-index.json` 去重并输出 `already_in_wiki:<page>`，再 fallback 到 raw library；同时新增 `discover-to-handoff`、`discovery-diagnostics.json`、selection policies，以及 hard/soft query-plan provenance。历史 source manifest 曾从 Paper Source `0.1.12` / Paper Wiki `0.1.5` 到 Paper Source `0.1.13` / Paper Wiki `0.1.6`，再到 Paper Source `0.1.14` / Paper Wiki `0.1.7`、Paper Source `0.2.1`、`0.2.2`、`0.2.3`、Paper Source `0.2.4` / Paper Wiki `0.2.3`、Paper Source `0.2.5` / Paper Wiki `0.2.4`、Paper Source `0.2.6` / Paper Wiki `1.0.0`、Paper Source `1.0.0`、`1.0.1`、`1.0.2`、`1.0.3`、`1.0.4`、`1.0.5`、`1.0.6` / Paper Wiki `1.0.0`；installed cache 曾见 Paper Source `1.1.0`、`0.1.11`、`0.1.10`、`0.1.8` 和 source `0.2.0`，因此 runtime claims 必须区分 source checkout、installed cache 和当前 Codex session。

2026-06-17 follow-up：Unpaywall 现在从 broad no-DOI 第一轮关键词检索默认源中移除。`plan_source_routing` 对 `search=doi-lookup` source 给出 `doi_lookup_source` demotion，只在 DOI 精确查询和采集阶段 OA fallback 中使用 Unpaywall；当前 live vault 配置也已移除首轮 `google_scholar` / `unpaywall`，保留 runtime env file 中的 Unpaywall email 供 DOI-backed OA fallback 使用。同日确认 `grok-search-rs 0.1.17` 在仅加载 OpenAI-compatible URL/model/key、未设置 `GROK_SEARCH_API_KEY` 时可完成 MCP initialize；源码只把 `GROK_SEARCH_API_KEY` 作为可选 alias 加入 whitelist，不要求用户配置 Grok 专用密钥。

## 能力快照

- 配置与安装：`config-setup`、`doctor --json`、`runtime.json`、provider readiness、`MINERU_TOKEN` set/missing 报告、paper-search MCP/CLI fallback、adaptive Python detection 和 `import paper_search_mcp` 探测。
- 论文发现：`discover-papers` 自然语言默认入口、用户画像/config 驱动的 query planner、agent-supplied `--query-variant` / `--domain-focus-term` / `--agent-query-plan-json`、wiki `_meta/reference-index.json` first dedupe、hard/soft query-plan provenance、request constraints (`--year-min`, `--code-policy`)、selection policies、`discovery-diagnostics.json`、`venue prior`、`domain ontology`、`two-stage retrieval`、`citation graph`、`evaluation set`、source routing、source coverage、EasyScholar default-on、review/survey 默认保留、`session_recommendations`、`auto_staging_plan` 和 `未核实` 指标。
- 论文推进：默认 discovery 只给候选和 wiki 去重；`discover-to-handoff` / `prepare-ranked --max-papers 10 --skip-existing` 是显式 source-staging 深入路径，包含 manual download card、identity check、MinerU Markdown/images、非空原生 TeX（若存在）、`mineru/mineru-manifest.json`、`MinerU reported done but produced no Markdown output` 明确错误。
- 读者与审查：reader/claim-support、`paper-quality-critic`、`parse-quality-critic`、critic quorum、source bundle audit 和 `paper-gate`。
- Wiki handoff：`wiki-ingest-handoff`、`record-human-approval`、显式 `codex-automation:<task-id>` approval metadata、`wiki-ingest-trigger`、`automation_handoff`、`record-wiki-ingest`、`wiki_ingest_recorded`、`waiting_for_human_gate`、`ready_for_agent=false`、`ready_after_human_approval=true`。
- Wiki ask：Paper Source `wiki-ask` 是 read-only formal graph / 程序化 fallback；Paper Wiki `ask_wiki` 是对话主入口。
- 生命周期：bounded lifecycle cleanup 使用 `retention.json`、默认 3000 files / 1 GiB、`over_budget=false` 视图、`run-lifecycle`、`raw-cleanup`、repository-maintenance、migrations、`wiki-reset`、formal-page-snapshots、tmp-manual-pdfs；preview 不刷新 `_paper_source/manifest.json`，不得删除 `_paper_source/raw`。
- 质量环：`Plugin Eval`、`paper-source-quality-gates`、benchmark、`evaluation-brief`、`paper-source-improvement-brief-v1`、`source_completeness` 和 `quality_loop_sources_complete`。

## 最近验证

最近可复用的验证信号：

```powershell
python -m pytest tests\paper_source -q  # 589 passed
python -m pytest tests\paper_source\test_config.py tests\paper_source\test_paper_search_adapter.py tests\paper_source\test_paper_discovery_query_planner.py tests\paper_source\test_orchestrator_dry_run.py -q  # 70 passed
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
3. 当前源码已进入 Paper Source `2.3.11`；当前机器历史上已把 `paperflow` marketplace source 切到本地 `<repo-root>`，并安装 Paper Source `1.1.0` 到 installed cache。`2.3.11` 仍需 marketplace refresh/reinstall/installed-cache verification 后才可声称运行态已更新；若要让 Git marketplace 用户获得同版本，还需要 commit/push 后再从 Git source upgrade。
4. 从新 Codex thread 运行 `doctor --json`、`config-status --json`、dry-run fixture smoke 和 `research-queue` 验证安装体验；当前 thread 不会重新加载刚安装的 skill metadata。
5. 对目标 vault 补齐 `AGENTS.md` 和 `_meta/*.md`，再让 Paper Wiki 消费 `wiki-ingest-brief.json` 和 reading report。

## 已知风险

- `docs/paper-source-linkage.md`、`docs/structure.md`、`docs/progress.md` 会增加 Plugin Eval deferred token 估算，但这些是当前维护材料，不应为了静态分数移出插件 docs。
- `paper-search` CLI、MinerU、Zotero 都是外部能力。缺失时应 warning 和引导，不应让只读诊断失败。
- `MINERU_TOKEN` 不得写入文档、日志、报告或配置预览，只能显示 set/missing。
- 当前机器的 Paper Source installed cache 已刷新到 `1.1.0`；开发源已是 `<repo-root>/plugins/paper-source` 的 `2.3.11`，用户级 `runtime.json` 不随 cache 版本目录替换。`2.3.11` 仍需 marketplace refresh/reinstall/installed-cache verification；Git marketplace 仍需 commit/push 后再 upgrade 才能让其他安装源看到同一版本。
- 最终 Obsidian/LLM Wiki 写入依赖目标 vault contract。Paper Source 只能提供 handoff 和 suggested routes，不能把固定脚本当成最终沉淀机制。
