# EPI 插件进度说明

更新时间：2026-06-04。本文档记录当前源码树的开发状态、已完成能力、已知风险和下一步计划。它是面向继续开发和发布验收的进度页，不替代 `docs/epi-linkage.md` 的链路契约，也不替代 `docs/structure.md` 的结构说明。

## 当前定位

EPI 当前聚焦“按用户画像/config 衍生的高质量论文收集和整理 -> Obsidian/LLM Wiki 知识沉淀 -> 轻阅读负担报告”。它是通用学术论文插件，不默认任何学科方向；AUV、机器人、AI、医学等词只能来自用户配置、当前请求或显式领域 hint。它不是自动完成选题、实验、写作、投稿的科研工作台。复现思路可以出现，但只作为阅读报告中的 compact caveat 和验证线索，不占主要篇幅。

## 已完成能力

- Marketplace 包装：`plugin.json` 已声明 EPI 展示信息、GitHub marketplace 链接、技能目录和默认提示；展示文案已从单一工程/机器人方向改成通用 academic/profile-driven 定位。
- 安装诊断：`doctor` 支持只读健康检查，区分插件结构错误和外部依赖 warning，并能给 `paper-search` 与 MinerU 配置链接。
- Runtime 配置：新增 `runtime_config.py`，从 `%USERPROFILE%\.codex\plugins\paper-search\epi\runtime.json` 自动加载 `paper-search` MCP、CLI fallback 和 MinerU env-file 路径；显式 env 优先，runtime.json 不保存 token 明文。
- Marketplace polish：`defaultPrompt` 已压到 3 条，避免 Codex 只使用前三条时丢失后续提示。
- 配置引导：`config-status`、`init-config`、`propose-config-update`、`apply-config-update` 已形成配置生命周期；当前新增 `config-setup` skill，把首次配置和修改配置改成聊天式逐步引导，完整脚本在 `docs/config.md`。
- Wiki 初始化：新增 `wiki-setup` skill，专门负责 paper research wiki vault 初始化和重置；初始化幂等补结构，并在 `<vault>\.git` 缺失时自动 `git init`，但不自动创建首个 commit。当前初始化把 EPI 运行产物统一收拢进 `_epi/`，根 `_meta/` 只保留正式 wiki contract 文件，并固定七类正式目录 `references/`、`concepts/`、`derivations/`、`experiments/`、`synthesis/`、`reports/`、`opportunities/`。重置必须盘点、备份计划和二次确认。已修正 reset 坑点并落到 CLI：`wiki-reset --preview` 可先列出影响路径，`wiki-reset` 默认重置 wiki 内容时保留 `_epi\meta\epi-config.yaml`、`_epi\meta\epi-config-state.json`、config history 和用户级 runtime.json；只有用户额外确认 `确认同时重置 EPI config` 并传入 `--reset-config-confirmed-by` 才允许删除或重置配置。`wiki-setup` 入口只保留边界与命令，详细恢复与误删清单放在 `skills/wiki-setup/references/reset-recovery.md`。现有旧 vault 可用 `epi-repository-migrate --preview --json` / `epi-repository-migrate --json` 把旧顶层 `_raw/_staging/_runs/_quarantine/_evolution` 收拢到 `_epi/`，再用 `epi-repository-cleanup --preview --json` 检查仓库清理策略。若发现误删、误操作或 config 意外缺失，skill 会停止后续论文流程，先用 `wiki-repair` 单入口检查，或用 `config-recover` 搜索 reset backups、config history 和 runtime.json 相关恢复线索，再用 `config-restore` 在确认后恢复。
- 论文发现：`dry-run` 支持候选标准化、过滤、ranking、报告、run index 和 research queue，且只写 `_epi/runs`。
- 发现输出：`paper-discovery` skill 已要求对话中先给“推荐优先看”清单，再给 EPI 实测证据；清单要包含本轮找到且保留下来的全部候选论文，并按阅读优先级排序。每篇推荐包含 venue/year、DOI、引用数、影响因子/分区或未核实、venue prior、PDF/代码可用性、方法场景、验证证据和 caveat。用户明确不要综述时，查询和 filter 会硬排除 review/survey 类结果。高质量检索新增 topic blocks、3-5 个 focused query variants、source routing、DOI/title 去重、wiki 已下载库去重、venue prior、Tier A/B/C 质量门控和 recall gap 记录，避免把 MCP 返回结果本身当成质量定义。
- 论文发现 skill bundle：`paper-discovery` 已蒸馏 `nature-academic-search` 和 academic-research-skills 的结构化组织方式，保留 English-first `SKILL.md` 作为入口，详细策略拆到 mode routing、离线 query planner、paper type taxonomy、ranking rubric、domain ontology、source tier、dedup engine、venue prior、two-stage retrieval、citation graph、evaluation set、multi-source workflow、anti-patterns 等 `references/` 分层文件；venue prior 现在明确是用户画像/config 驱动，领域 curated list 只能作为对应用户领域的 prior，论坛/社区榜单只能作为弱召回线索，影响因子、分区、引用数等仍需实时或可信来源核验。
- 主题纵向层：新增 `topic-tracking` skill，把持续方向跟踪、net-new 增量、backlog priority、coverage gap、systematic-review snowballing、parse fidelity 和 acquisition fallback 从单轮 `paper-discovery` 中拆出，避免 per-paper 管道替代主题认知账本。
- Skill 入口语言：`plugins/epi/skills/*/SKILL.md` 已重构为 English-first 入口说明，保留少量中文 onboarding/确认短语作为用户交互和 CLI gate 契约；`paper-discovery/README.md` 已移除，避免违反 skill-creator 对顶层 README 的精简要求。
- 精准检索计划：`skills/paper-discovery/scripts/query-planner.py` 可把用户画像/config 和用户主题转换成 `query_plan`，包含 `research_mode`、profile、概念块、`domain_focus_terms`、5-8 条 query variants、source route、recall gap checks 和 quality signals；默认 `dry-run` 已接入 query plan，会写 `query-plan.json`，按 query variants 多次搜索并合并 candidate pool；`dry-run --json` 可打印 run id 和关键 artifact 路径，方便 agent 串联；默认排除 review/survey/meta 类综述候选，用户明确找综述时才放开。EPI 不再把 AUV/机器人/AI 等词作为全局默认，而是从 `_epi\meta\epi-config.yaml` 的 profile、domains、positive_keywords、negative_keywords、venue_prior 和当前请求衍生检索词；query plan 的扩展词只用于召回，`domain_focus_terms` 才是 narrow topic 的硬锚点，ranking 的画像匹配词使用用户 config 和当前请求核心词，避免宽召回词稀释窄主题相关性；`rank.json` 现在记录 `paper_type`、`paper_classification`、`quality_gate`、`quality_tier`、`ranking_rubric` 和 `ranking_confidence`，用于解释阅读优先级；若 profile-derived 计划偏离当前请求，使用 `--no-query-plan` 精确短语查询或先更新 config。
- 默认快路：`prepare-ranked` 支持从 dry-run 的 `rank.json` 直接完成 selected ranked paper acquire + MinerU parse + source-staging 报告，并停在 human approval / final wiki writing 之前。默认 `fast-ingest` 不跑 reader/critic；`reviewed-ingest` 才加 reader；`audited-ingest` 才加 reader+critic。实测批量用 `--max-papers 10 --skip-existing`，补跑时只有 `parse-record.json status=success`、MinerU companion artifacts 完整且同模式 `promotion-plan.json` 已存在的论文才不占预算；`--max-papers 1` 只作为 smoke test；`--json` 会输出 prepared run id、source run id、processed/skipped counts、`stops_after=source-staging` 和关键 report artifact 路径，方便 agent 串联。单篇下载/解析异常会记录为该论文的失败状态并继续后续候选。
- 推进采集：`advance-ranked`、`advance-paper`、`advance-batch`、`ingest-one` 支持从候选论文进入 raw artifact、MinerU 解析、source-staging；可用 `--mode reviewed-ingest` / `--mode audited-ingest` 按需加入 reader/critic。
- MinerU 产物整理：成功解析后最终产物只保留在 `mineru/`，大型 `mineru-command/paper` 与 `mineru-command/parsed` 工作副本会清理；若 MinerU 没有原生 TeX，生成非空 Markdown-derived LaTeX fallback 并记录 `tex_source`。若 MinerU stdout 显示任务 done 但没有 Markdown，错误会明确记录为 `MinerU reported done but produced no Markdown output` 并保留工作目录用于诊断。
- Reader v2：已拆出三角色阅读输出、evidence map、claim support map、证据地址校验和轻阅读报告所需摘要；`reader/claim-support.json` 会区分 source-grounded、metadata-only、inferred 与 unsupported claim。
- Critic 质量门：`paper-quality-critic` 已从文件存在检查升级为学术论文可靠性检查，覆盖身份、claim support、benchmark integrity、复现信息 warning、scope overclaim 和 parse-vs-paper failure；`parse-quality-critic` 现在把 `mineru/<slug>.md`、`mineru/paper.tex`、`mineru/images/*`、`mineru/mineru-manifest.json` 和 `parse-record.json` 视为一组 source-first 物化证据。
- Role critic quorum：Nature/Sci editor、peer reviewer、senior domain researcher 的角色审查已经进入 critic quorum 和后续 decision。
- Source-staging 和报告：默认 fast-ingest 在源材料完整后生成 `wiki-ingest-brief.json`、`wiki_deposition_task.json`、`promotion-plan.json` 和 `briefs/reading-report.md`；audited-ingest 需要 critic pass。阅读报告是中文优先的人工确认报告，不是正式 wiki 页面。
- EPI paper deposition adapter：新增 `epi-paper-deposition` skill，作为 EPI source bundle / `wiki_deposition_task.json` 到 obsidian-wiki skill layer 的正式 adapter；旧 `epi-wiki-deposition` 只保留为 compatibility alias。
- Agent-mediated wiki ingest：默认不由固定脚本写最终 wiki，而是生成 `wiki-ingest-handoff` 和 `wiki_deposition_task.json`，要求 agent 通过 `epi-paper-deposition` 显式使用 `llm-wiki`、`wiki-ingest`、`wiki-context-pack`、`wiki-lint`、`wiki-stage-commit`、`wiki-status`、`wiki-query`、`wiki-provenance`、`tag-taxonomy`，并读取目标 vault contract 后再写入。
- Wiki provenance 层：新增 `wiki-provenance` skill，专门约束最终页上的 claim support status、evidence address、page-local provenance block 和 round-trip retrieval hook，避免 `reader/claim-support.json` 与 `reader/evidence-map.json` 只留在 EPI sidecar 中。
- 中文链路与结构总览：新增 `docs/overview.zh.md`，作为继续开发和交接时的中文导航，把主题纵向层、单篇证据层、wiki provenance 层、主要 CLI、artifact 路径、skill 分工和安全边界集中说明；权威流程语义仍以 `docs/epi-linkage.md` 和 `docs/structure.md` 为准。
- Agent-mediated 前置批准：新增 `record-human-approval --scope run-wiki-ingest-agent`，只在当前 `paper-gate` 无 failure checks 且唯一待办为 `human-approval` 时写 `_epi/staging/papers/<slug>/human-approval.json`；批准后 `wiki-ingest-handoff` 才显示 `ready_for_agent=true`。
- Agent-mediated 继续触发：新增 `wiki-ingest-trigger --slug <slug>`，批准后写 `_epi/staging/papers/<slug>/wiki-agent-trigger.json`，让当前 Claude、Codex 或其他 wiki-capable agent 在用户再次触发 `@EPI` 时继续最终 wiki 写入；它不后台启动外部 LLM 进程，也不写最终 wiki 页。
- Agent-mediated 完成态记录：`record-wiki-ingest` 在外部 wiki ingest agent 写完最终 Markdown 页后，EPI 只读最终页并记录相对路径、sha256、pre-write human approval、`paper-gate` 摘要和 source-first handoff 元数据；该命令要求 `--approved-by` 与 `human-approval.json` 一致，并在记录前验证 formal frontmatter、`category/page_family`、sources、provenance、Obsidian wikilinks、forbidden formula blocks 和 family-specific gates，不修改最终页、manifest、index、log 或 hot。
- Zotero record-only sidecar：`record-wiki-ingest` 和 legacy `promote-to-wiki` 会根据 vault config 写 `_epi/raw/papers/<slug>/zotero-record.json`，记录 skipped/recorded 状态、collection、论文 metadata、wiki ingest 摘要和 final page hashes；结果同步进入 `report.json`、`run-state.json`、`_epi/runs/index.json` 和 dashboard，不调用外部 Zotero API。
- Paper gate：`paper-gate` 提供 GitHub checks 风格只读质量门；`research-queue --actions` 以当前 gate 为准推荐下一步。
- Report step：公开 CLI `report --run-id <run-id> [--json]` 是 workflow image 的 Report surface；它读取已有 `_epi/runs/<run-id>/report.md`、`report.json` 和 `run-state.json`，不重新运行 discovery/ingest/MinerU/staging/Zotero/wiki 写入。内部模块名是 `report_run.py`，文档和 skill surface 不应把它写成不存在的 `run-report` 命令。
- Legacy promotion：`promote-to-wiki` 和 `rollback-promotion` 只保留旧 compiled-draft 路径，带路径安全限制和人工确认。
- Self-evolution：`propose-evolution`、`activate-evolution`、`evolution-query` 已采用 proposal-based、human approval、validation gate 和 metric comparison。
- 插件开发质量环：新增 `evaluation-brief`，把 Plugin Eval、`epi-quality-gates` metric pack、benchmark 和 before/after metrics 合并成 `epi-improvement-brief-v1`，同时生成可喂给 `propose-evolution` 的 `proposed_evolution` payload。该 brief 现在会显式记录 `source_completeness`，并在缺失任一证据源时把 `quality_loop_sources_complete` 作为必须补齐的 gate；`activate-evolution` 会在执行点拒绝仍带有 `missing_sources` 或 `invalid_sources` 的该 gate，即使外层 validation result 写了 `passed=true`。
- 查询与维护：`runs-query`、`research-queue`、`wiki-query` 支持状态查询；redo/recritic 支持阶段性修复，audited-ingest 不绕过 critic gate。
- 过渡态生命周期：`run-lifecycle` 支持 `_epi/runs` 单次 run 目录 dry-run/apply 清理，保留面板文件并写 `_epi/meta/run-lifecycle` manifest；EPI run 结束后会自动检查 `_epi/runs`，超过 15 个单次 run 目录时自动应用 cleanup，保留最新 15 个 terminal run 并按 workflow 至少保留 2 个；`epi-repository-cleanup` 会按 `_epi/policies/retention.json` 检查内部仓库总文件数/体积，默认优先清 terminal run 等可再生产物，不删除 `_epi/raw/papers` 原始论文源；发现阶段会和 `_epi/raw/papers` 已下载论文按 DOI/arXiv/title 去重，避免重复推荐。

## 本轮相关变更范围

本轮 EPI stability / skill-based-architecture 对齐范围是：把实跑暴露的 raw bundle 完整性、record-wiki-ingest 严格校验、run index 原子写入、Obsidian graph filter、formal wiki 中文正文偏好、agent context policy 和 Codex 子代理授权规则固化到代码、测试、routing 和 docs 中；插件版本同步到 `0.1.3`。

- `plugins/epi/AGENTS.md`
- `plugins/epi/skills/routing.yaml`
- `plugins/epi/skills/run-lifecycle/SKILL.md`
- `plugins/epi/scripts/build/epi/source_bundle_audit.py`
- `plugins/epi/scripts/build/epi/graph_visibility.py`
- `plugins/epi/scripts/build/epi/wiki_language.py`
- `plugins/epi/scripts/build/epi/wiki_handoff_contracts.py`
- `plugins/epi/scripts/build/epi/wiki_record_workflows.py`
- `plugins/epi/scripts/build/epi/wiki_ingest_handoff.py`
- `plugins/epi/scripts/build/epi/wiki_ingest_trigger.py`
- `plugins/epi/scripts/build/epi/wiki_ingest_record.py`
- `plugins/epi/scripts/build/epi/run_index.py`
- `plugins/epi/docs/structure.md`
- `plugins/epi/docs/workflow.md`
- `tests/epi/test_source_bundle_audit.py`
- `tests/epi/test_wiki_init.py`
- `tests/epi/test_wiki_ingest_handoff.py`
- `tests/epi/test_wiki_ingest_record.py`
- `tests/epi/test_paper_gate.py`
- `tests/epi/test_current_docs.py`

本轮 P0 安全门完善范围是：把 agent-mediated wiki ingest 前的人类批准从 handoff 提醒升级为可验证 artifact，并把 development quality loop 的 source completeness gate 升级为 activation-time hard gate：

- `plugins/epi/scripts/build/epi/wiki_ingest_approval.py`
- `plugins/epi/scripts/build/epi/wiki_ingest_handoff.py`
- `plugins/epi/scripts/build/epi/wiki_ingest_record.py`
- `plugins/epi/scripts/build/epi/paper_gate.py`
- `plugins/epi/scripts/build/epi/skill_aware_evolve.py`
- `plugins/epi/scripts/build/epi/cli.py`
- `plugins/epi/scripts/build/epi/orchestrator.py`
- `plugins/epi/docs/epi-linkage.md`
- `plugins/epi/docs/structure.md`
- `plugins/epi/docs/workflow.md`
- `plugins/epi/docs/evaluation.md`
- `plugins/epi/skills/paper-ingest/SKILL.md`
- `plugins/epi/skills/skill-aware-evolve/SKILL.md`
- `tests/epi/test_cli_parser.py`
- `tests/epi/test_paper_gate.py`
- `tests/epi/test_wiki_ingest_handoff.py`
- `tests/epi/test_wiki_ingest_record.py`
- `tests/epi/test_optional_integrations.py`

本轮补齐 workflow image 中 Report step、非机器人 profile 证明和开发质量环 source completeness：

- `plugins/epi/docs/epi-linkage.md`
- `plugins/epi/docs/evaluation.md`
- `plugins/epi/docs/structure.md`
- `plugins/epi/docs/workflow.md`
- `plugins/epi/docs/progress.md`
- `plugins/epi/.codex-plugin/plugin.json`
- `plugins/epi/build/metric-packs/epi-quality-gates/emit-epi-quality-gates.js`
- `plugins/epi/scripts/build/epi/cli.py`
- `plugins/epi/scripts/build/epi/evaluation_loop.py`
- `plugins/epi/scripts/build/epi/query_planner.py`
- `plugins/epi/scripts/build/epi/report_run.py`
- `plugins/epi/skills/paper-discovery/SKILL.md`
- `plugins/epi/skills/paper-ingest/SKILL.md`
- `plugins/epi/skills/skill-aware-evolve/SKILL.md`
- `README.md`
- `tests/epi/test_current_docs.py`
- `tests/epi/test_config_onboarding_docs.py`
- `tests/epi/test_evaluation_loop.py`
- `tests/epi/test_metric_pack.py`
- `tests/epi/test_paper_discovery_query_planner.py`
- `tests/epi/test_runs_query_cli.py`

对齐目标是：保留 EPI profile-driven 通用定位；把 Report step 固定为读取既有 run report artifact 的只读 surface，真实命令是 `python scripts\orchestrator.py report --run-id <run-id> --vault <vault> [--json]`；让 JSON 输出包含 `run_state` payload；明确 `report_run.py` 是内部生成/读取模块，当前代码库没有独立 `run-report` CLI；用非机器人 biomedical/genomics profile 回归证明 query planner 不加载机器人默认；让 `evaluation-brief` 在缺 Plugin Eval、`epi-quality-gates` 或 benchmark/comparison JSON 时记录 `source_completeness.complete=false`、`missing_sources` 和 `quality_loop_sources_complete` gate。

本轮新增 agent-mediated wiki ingest 完成态记录，并追加 Zotero record-only sidecar，让“wiki ingest agent 已按目标 vault contract 写完最终页”从口头状态升级为可审计 artifact，同时把可选 Zotero 后续动作挂到同一证据链：

- `plugins/epi/scripts/build/epi/wiki_ingest_record.py`
- `plugins/epi/scripts/build/epi/cli.py`
- `plugins/epi/scripts/build/epi/orchestrator.py`
- `plugins/epi/scripts/build/epi/paper_gate.py`
- `plugins/epi/scripts/build/epi/zotero_sync.py`
- `plugins/epi/scripts/build/epi/report_run.py`
- `plugins/epi/scripts/build/epi/run_index.py`
- `plugins/epi/docs/epi-linkage.md`
- `plugins/epi/docs/structure.md`
- `plugins/epi/docs/workflow.md`
- `plugins/epi/skills/zotero-sync/SKILL.md`
- `plugins/epi/skills/paper-ingest/SKILL.md`
- `tests/epi/test_wiki_ingest_record.py`
- `tests/epi/test_run_index_dashboard.py`
- `tests/epi/test_optional_integrations.py`
- `tests/epi/test_report_run.py`
- `tests/epi/test_cli_parser.py`

这些改动的目标是：不替目标 vault agent 写最终 wiki，而是把 agent 已完成的最终页路径、hash、approval、paper-gate 状态和 source-first handoff 元数据记录进 EPI raw/staging/run 报告。记录后 `paper-gate` 进入 `status=wiki_ingest_recorded`、`next_action=review-recorded-wiki-pages`，后续 Zotero/report/run index/人工复核有真实 final page paths 可消费；Zotero 默认只写本地 sidecar，外部 API 同步仍保持显式 opt-in。

上一轮新增质量环集中在把流程图底部的 Plugin Eval -> `epi-quality-gates` -> benchmark -> before/after compare -> improvement brief -> skill-aware-evolve proposal 变成可执行 contract：

- `plugins/epi/scripts/build/epi/evaluation_loop.py`
- `plugins/epi/scripts/build/epi/cli.py`
- `plugins/epi/scripts/build/epi/orchestrator.py`
- `plugins/epi/build/metric-packs/epi-quality-gates/emit-epi-quality-gates.js`
- `plugins/epi/docs/evaluation.md`
- `plugins/epi/docs/epi-linkage.md`
- `plugins/epi/docs/structure.md`
- `tests/epi/test_evaluation_loop.py`
- `tests/epi/test_metric_pack.py`
- `tests/epi/test_cli_parser.py`
- `tests/epi/test_current_docs.py`

这些改动的目标是：把“评估发现问题 -> 生成改进证据 -> 进入受控 skill-aware evolve”的路径从人工口头约定升级为机器可读 artifact 和可测试质量门。它不直接修改 skill/template，也不自动应用配置；真正变更仍需要 `propose-evolution`、human approval 和 validation gates。

上一轮新增修复集中在插件 cache 环境不继承手工 `.env`、完整链路实测和 1-3 raw preparation 暴露的问题：

- `plugins/epi/scripts/build/epi/cli.py`
- `plugins/epi/scripts/build/epi/orchestrator.py`
- `plugins/epi/scripts/build/epi/run_mineru_parse.py`
- `plugins/epi/scripts/build/epi/runtime_config.py`
- `plugins/epi/scripts/build/epi/doctor.py`
- `plugins/epi/scripts/build/epi/paper_search_adapter.py`
- `plugins/epi/docs/config.md`
- `plugins/epi/docs/workflow.md`
- `plugins/epi/docs/epi-linkage.md`
- `plugins/epi/docs/progress.md`
- `plugins/epi/.codex-plugin/plugin.json`
- `plugins/epi/skills/paper-discovery/SKILL.md`
- `plugins/epi/skills/paper-discovery/scripts/query-planner.py`
- `plugins/epi/skills/paper-discovery/references/*.md`
- `plugins/epi/skills/paper-ingest/SKILL.md`
- `plugins/epi/skills/mineru-paper-parser/SKILL.md`
- `tests/epi/test_normalize_filter_rank.py`
- `tests/epi/test_batch_advance_router.py`
- `tests/epi/test_cli_parser.py`
- `tests/epi/test_config_onboarding_docs.py`
- `tests/epi/test_mineru_parse_adapter.py`

这些改动的目标是：用仓库源插件 `<plugin-root>` 把 1-3 路径固定成 `dry-run -> prepare-ranked`，完成发现、下载、MinerU 解析后精确停止，不再手工复制 candidate JSON，也不误触发 reader/critic/staging；同时让安装后的插件线程能自动读取用户级 runtime.json，不再依赖手工 source 本机 `.env`。修复点包括：`prepare-ranked` 识别 0 KB TeX 等不完整 parse 并重新解析；MinerU 成功后清理重复工作目录；MinerU 无原生 TeX 时生成非空 LaTeX fallback；doctor/discovery/download/parse 前自动加载 MCP/CLI/MinerU runtime 配置。

最近几次实测新增失败点和修复：

- 失败点：skill 把 `--max-papers 1` 写成常用 1-3 命令，导致用户实测只看到两篇。修复：skill 区分 smoke test 和实测批量，实测使用 `--max-papers 10 --skip-existing`。
- 失败点：单篇 `paper-search` 下载超时会让整个 `prepare-ranked` 中断。修复：下载 timeout 结构化记录，`prepare-ranked` 逐篇隔离异常并继续。
- 失败点：补跑时已解析论文占用 `max-papers` 预算。修复：新增 `--skip-existing`。
- 失败点：CLI parser 已接受 `--skip-existing`，但 handler 曾把参数接到 `advance-ranked` 且没有传给 `prepare-ranked`。修复：更正 handler 路由，并新增 CLI handler 级测试，防止 parser-only 测试漏掉实测调用链。
- 失败点：query planning 曾把用户实测里的 AUV/RL 当成项目默认，容易让通用插件变成单学科插件。修复：query planner 改为 config/profile-first，AUV/机器人/AI 只在用户画像、当前请求或显式 domain hint 中出现时参与扩展。
- 失败点：用户配置 + 当前主题触发 query plan 后，宽召回扩展词曾被直接并入 ranking 正向关键词，导致高相关候选因没有命中所有扩展词被误降为 `review-candidate`，后续 `advance-ranked` 默认跳过而看起来“成功但没推进”。修复：query plan 扩展词只参与召回，ranking 画像词收窄到 config 和当前请求核心词，并给 `dry-run --json` 增加机器可读 artifact 输出。
- 失败点：filter/ranking/reader 中仍残留机器人默认兜底，和“所有学科可用”的插件定位冲突。修复：filter 使用 config domains、`domain_focus_terms` 或 query_plan domain_terms；ranking 使用 config/profile/query_plan 衍生关键词和 configured venue_prior；reader/domain critic 改为用户配置画像表述。
- 失败点：实测宽召回 AUV 查询时，`vehicle trajectory tracking` 这类从长 query 切出的宽泛 n-gram 曾进入 `domain_focus_terms`，让 ground vehicle / racing vehicle 候选只靠任务词通过 hard gate。修复：当当前请求触发明确领域 hint 时，hard gate 使用该 hint 的强同义词和用户配置域词；宽泛 n-gram 只保留在召回/query 侧，不单独放行。
- 失败点：安装版 `0.1.0+codex.20260531111632` 实测 AUV/RL/control 非综述查询时，`not review` 只触发 review 排除，没有连带排除 survey/meta；部分 `A Survey...`、`surveys recent advances` 和泛 autonomous vehicles 结果进入 `rank.json`。修复：显式非综述请求统一使用完整 review/survey/meta 文档类型排除；源码版复测 run `20260531T034732053575Z` 中 `rank.json` 从 60 个 raw candidates 收敛到 3 个 AUV/control 相关候选，Survey/Review、Blockchain autonomous vehicles、泛 RL 均进入 rejected。
- 失败点：`run-lifecycle` 只有手动命令和 skill，没有被主链路自动接管；默认 `keep-latest=30` 时用户实测 `_runs` 已堆到 17 个目录仍不会清理。修复：默认 `keep-latest=15`，并在 dry-run / batch advance / prepare-ranked 结束后自动检查和应用 lifecycle cleanup，仍只删除 `_runs` 下 terminal 单次 run 目录，不碰 dashboard/index、`_raw`、`_staging`、配置或 Zotero。
- 失败点：安装版 `prepare-ranked` 没有 `--json`，实测后续只能解析文本输出，降低 agent 自动跟踪稳定性。修复：为 `prepare-ranked` 增加机器可读 JSON 输出，并同步 workflow 与 paper-discovery/paper-ingest skill。
- 失败点：出版社 PDF 403/502 被误解为“没有论文”。修复：skill 将其标为 acquisition evidence，并要求尝试开放来源或 arXiv-first rerun。
- 失败点：MinerU stdout 显示 done 但无 Markdown 时错误过泛。修复：记录明确错误文本和 batch id。

## 最近验证

本轮 source-first wiki 记录闭环已验证：

```powershell
python -m pytest tests\epi\test_reader_evidence_module.py tests\epi\test_reader_v2_role_outputs.py -q --basetemp .pytest_tmp_epi_reader_source_first
python -m pytest tests\epi\test_wiki_ingest_record.py tests\epi\test_wiki_ingest_handoff.py tests\epi\test_one_paper_ingest.py tests\epi\test_cli_parser.py -q --basetemp .pytest_tmp_epi_wiki_source_review
python -m pytest tests\epi\test_current_docs.py tests\epi\test_epi_linkage_doc.py tests\epi\test_config_onboarding_docs.py -q --basetemp .pytest_tmp_epi_docs_sync
python -m pytest tests\epi -q --basetemp .pytest_tmp_epi_full_current
```

结果：reader/source-review 聚焦回归为 `9 passed in 0.32s`；wiki ingest/source review 聚焦回归为 `42 passed in 1.54s`；docs 同步回归为 `17 passed in 3.63s`；全量 `tests\epi` 为 `299 passed in 30.21s`。

本轮 Report / evaluation / query planner / docs 对齐后已验证：

```powershell
python -m pytest tests\epi\test_runs_query_cli.py tests\epi\test_evaluation_loop.py tests\epi\test_metric_pack.py tests\epi\test_paper_discovery_query_planner.py tests\epi\test_current_docs.py tests\epi\test_config_onboarding_docs.py tests\epi\test_epi_linkage_doc.py -q --basetemp .pytest_tmp_epi_round2_focused
```

结果：聚焦回归为 `53 passed in 4.94s`。

本轮 discovery/ranking `quality_gate` 补丁后已验证：

```powershell
python -m pytest tests\epi\test_ranking_protocol.py tests\epi\test_report_run.py tests\epi\test_orchestrator_dry_run.py tests\epi\test_current_docs.py tests\epi\test_config_onboarding_docs.py -q --basetemp .pytest_tmp_epi_quality_gate_focused2
python -m pytest tests\epi\test_paper_discovery_query_planner.py tests\epi\test_normalize_filter_rank.py tests\epi\test_ranking_protocol.py tests\epi\test_paper_search_adapter.py tests\epi\test_orchestrator_dry_run.py -q --basetemp .pytest_tmp_epi_quality_gate_discovery
python -m pytest tests\epi -q --basetemp .pytest_tmp_epi_quality_gate_full
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\release_check_epi.ps1 -PytestTarget tests/epi
```

结果：quality-gate 聚焦回归为 `37 passed in 11.04s`；discovery/ranking 扩展回归为 `45 passed in 10.19s`；全量 `tests\epi` 为 `287 passed in 30.16s`；release check 通过，内部 pytest 为 `287 passed in 31.73s`，本地未设置的 skill/plugin/Plugin Eval validators 按脚本契约跳过。

本轮 Zotero sidecar、report 和 run index 补丁后已验证：

```powershell
python -m pytest tests\epi\test_wiki_ingest_record.py tests\epi\test_optional_integrations.py tests\epi\test_report_run.py tests\epi\test_run_index_dashboard.py -q --basetemp .pytest_tmp_epi_zotero_report_focused
python -m pytest tests\epi\test_current_docs.py tests\epi\test_epi_linkage_doc.py -q --basetemp .pytest_tmp_epi_zotero_docs
python -m pytest tests\epi -q --basetemp .pytest_tmp_epi_zotero_full
```

结果：Zotero/report/run-index 聚焦回归为 `37 passed in 0.92s`；docs/linkage 聚焦回归为 `8 passed in 3.47s`；全量 `tests\epi` 为 `287 passed in 29.83s`。

本轮新增完成态记录后已验证：

```powershell
python -m pytest tests\epi\test_wiki_ingest_record.py tests\epi\test_paper_gate.py tests\epi\test_cli_parser.py -q --basetemp .pytest_tmp_epi_record_focused1
python -m pytest tests\epi\test_wiki_ingest_record.py tests\epi\test_paper_gate.py tests\epi\test_cli_parser.py tests\epi\test_current_docs.py tests\epi\test_epi_linkage_doc.py tests\epi\test_config_onboarding_docs.py -q --basetemp .pytest_tmp_epi_record_docs1
python -m pytest tests\epi -q --basetemp .pytest_tmp_epi_record_full1
python <plugin-creator-validate-script> <plugin-root>
python <skill-creator-quick-validate-script> <plugin-root>\skills\paper-ingest
.\scripts\release_check_epi.ps1 -PytestTarget tests/epi/test_wiki_ingest_record.py
rg -n "<local-machine-paths-regex>" plugins\epi
```

结果：`record-wiki-ingest` 聚焦 parser/gate 回归为 `39 passed in 1.12s`；docs/skill 相关聚焦回归为 `56 passed in 4.70s`；全量 `tests\epi` 为 `285 passed in 30.40s`；EPI plugin validation passed；`paper-ingest` skill quick validation passed；release check 对 `tests/epi/test_wiki_ingest_record.py` 为 `5 passed in 0.65s` 并通过；本机绝对路径泄漏检查无命中。

本轮已验证：

```powershell
python -m pytest tests\epi\test_cli_parser.py tests\epi\test_batch_advance_router.py::test_prepare_ranked_papers_can_skip_existing_parsed_candidates_when_resuming tests\epi\test_batch_advance_router.py::test_prepare_ranked_papers_records_failed_candidate_and_continues -q --basetemp=.pytest_tmp_cli_skip_existing_fix
python -m pytest tests\epi -q --basetemp=.pytest_tmp_epi_failure_summary_full_final
python -m pytest tests\epi\test_paper_discovery_query_planner.py tests\epi\test_cli_parser.py::test_dry_run_parser_accepts_profile_derived_query_plan_domain tests\epi\test_config.py tests\epi\test_config_onboarding_docs.py tests\epi\test_current_docs.py tests\epi\test_orchestrator_dry_run.py::test_dry_run_writes_phase_1_artifacts tests\epi\test_orchestrator_dry_run.py::test_dry_run_query_plan_searches_variants_and_merges_candidate_pool tests\epi\test_orchestrator_dry_run.py::test_dry_run_with_generic_config_derives_filter_terms_from_query_plan tests\epi\test_role_critic_quorum.py::test_critic_quorum_includes_role_specific_reviewers_for_reader_v2_outputs -q --basetemp=.pytest_tmp_epi_profile_query_focused2
python -m pytest tests\epi -q --basetemp=.pytest_tmp_epi_profile_generic_full_final
python <plugin-creator-validate-script> <plugin-root>
python -m pytest tests\epi\test_paper_search_adapter.py tests\epi\test_batch_advance_router.py -q --basetemp=.pytest_tmp_prepare_resilience_related
python -m pytest tests\epi\test_cli_parser.py::test_prepare_ranked_parser_accepts_skip_existing_for_resumable_batches tests\epi\test_batch_advance_router.py::test_prepare_ranked_papers_can_skip_existing_parsed_candidates_when_resuming tests\epi\test_mineru_parse_adapter.py::test_mineru_command_reports_done_without_markdown_as_missing_output -q --basetemp=.pytest_tmp_epi_skillopt_green
python -m pytest tests\epi\test_config_onboarding_docs.py::test_epi_skills_document_precise_one_to_three_prepare_ranked_path tests\epi\test_config_onboarding_docs.py::test_paper_discovery_reference_files_exist_and_hold_split_protocol -q --basetemp=.pytest_tmp_epi_skill_docs_green
python -m pytest tests\epi\test_runtime_config.py tests\epi\test_doctor_cli.py tests\epi\test_config_onboarding_docs.py -q
python -m pytest tests\epi\test_mineru_parse_adapter.py tests\epi\test_cli_parser.py tests\epi\test_batch_advance_router.py tests\epi\test_config_onboarding_docs.py -q --basetemp=.pytest_tmp_one_to_three_related2
python -m pytest tests\epi -q --basetemp=.pytest_tmp_one_to_three_full
python <skill-creator-quick-validate-script> <plugin-root>\skills\paper-discovery
python <skill-creator-quick-validate-script> <plugin-root>\skills\paper-ingest
python <skill-creator-quick-validate-script> <plugin-root>\skills\mineru-paper-parser
python <plugin-creator-validate-script> <plugin-root>
python -m pytest tests\epi\test_paper_quality_critic_protocol.py -q --basetemp=.pytest_tmp_green_paper_quality
python -m pytest tests\epi\test_redo_recritic.py::test_recritic_cli_writes_routed_report_with_changed_artifacts tests\epi\test_paper_quality_critic_protocol.py -q --basetemp=.pytest_tmp_green_recritic_and_quality
python -m pytest tests\epi -q --basetemp=.pytest_tmp_full_chain_fix
python -m pytest tests\epi -q --basetemp=.pytest_tmp_release_full_chain_fix2
python -m coverage run -m pytest tests\epi -q --basetemp=.pytest_tmp_release_cov_full_chain_fix
python -m coverage run -m pytest tests\epi -q --basetemp=.pytest_tmp_epi_runtime_cov
python -m coverage xml -o plugins\epi\coverage\coverage.xml
python <plugin-creator-validate-script> <plugin-root>
python <skill-creator-quick-validate-script> <plugin-root>\skills\mineru-paper-parser
node <plugin-eval.js> analyze <plugin-root> --format markdown
```

结果：最新质量环聚焦回归为 `36 passed in 5.42s`；最新全量 `tests\epi` 为 `279 passed in 37.63s`；EPI plugin validation passed；`epi-quality-gates` metric pack 在源码插件上返回 pass rate `1`；轻量 `scripts\release_check_epi.ps1 -PytestTarget tests/epi/test_evaluation_loop.py` 为 `3 passed in 0.60s`，且插件包未发现本机绝对路径泄漏。历史 coverage run 为 `211 passed in 19.92s`，`plugins\epi\coverage\coverage.xml` 已刷新；历史 Plugin Eval 结果为 `82/100`、`0 fail, 4 warn`、coverage `93.49%`；remaining warnings 为 token budget 和 Windows 路径下 `py-tests-missing` 识别限制。

1-3 真实目录整理结果如下。这是旧目录结构下的历史实测样例，不代表 EPI 的默认研究方向；当前新初始化和迁移后的 vault 使用 `_epi/raw`、`_epi/runs`、`_epi/staging`。

- 论文 raw root：`<vault>\_raw\papers\a-survey-learning-embodied-intelligence-from-physical-simulators-and-world-models`。
- canonical MinerU Markdown：`330048` bytes。
- `mineru\paper.tex`：`336909` bytes，`tex_source=markdown-fallback`。
- `mineru\images`：`68` files。
- `work_dir_retention=logs-only`。
- `mineru-command\paper` 与 `mineru-command\parsed` 已清理，只保留 stdout/stderr 日志。

真实链路实测结果。这同样是旧目录结构下的历史实测样例；当前等价 artifact 位于 `_epi/...`：

- 发现 run：`<vault>\_runs\20260529T191647886910Z`，MCP 优先调用，MCP 返回 0 篇后记录 fallback，CLI fallback 找到 `A Survey on Robotics with Foundation Models: toward Embodied AI`。
- 论文 raw root：`<vault>\_raw\papers\a-survey-on-robotics-with-foundation-models-toward-embodied-ai`。
- 修复前状态：`critic_failed`，阻断项为 `benchmark_integrity`。
- 修复后 `recritic`：`critic-quorum.json` 六个 reviewer 全部 pass，`paper-quality-critic` 记录 `benchmark_integrity: no explicit outperform/SOTA claim detected`。
- `advance-paper` 后状态：`staged`，`next_action=run-wiki-ingest-agent`。
- `paper-gate --json`：`status=waiting_for_human_gate`，`failure_checks=[]`，仅 `human-approval` action required。
- `wiki-ingest-handoff --json`：human approval 未记录前 `ready_for_agent=false`、`ready_after_human_approval=true`，handoff artifacts 位于 `_staging\papers\<slug>`。

## 发布前必须重跑

```powershell
python -m pytest tests\epi -q --basetemp .pytest_tmp_epi_current
python <plugin-creator-validate-script> <plugin-root>
python -m coverage run -m pytest tests\epi
python -m coverage xml -o plugins\epi\coverage\coverage.xml
node <plugin-eval.js> analyze <plugin-root> --format markdown
```

验收标准：

- 源码测试通过。
- EPI plugin validation 通过。
- Plugin Eval 无 fail，分数不低于 `70/100`。
- coverage artifact 可被 Plugin Eval 识别。
- 若仍有 Windows `py-tests-missing` warning，需记录为评估器路径识别限制，而不是删除源码测试。

## 下一步计划

1. 发布本轮修复 commit，并从 GitHub/marketplace 重新安装 EPI，确认安装 cache 版本变为当前 `plugin.json` 中的版本。
2. 升级安装副本后，从新 Codex thread 用 `@epi` 运行 `doctor --json`、`config-status --json`、dry-run fixture smoke 和 `research-queue` 验证安装体验。
3. 对 `<vault>` 补齐目标 vault contract 文件（例如 `AGENTS.md` 和 `_meta/*.md`），这样 wiki-ingest agent 能按本 vault 的最终规则落页，而不是只依赖 EPI suggested routes。
4. 记录 human approval 后，交给 wiki-ingest agent 消费 `_epi\staging\papers\a-survey-on-robotics-with-foundation-models-toward-embodied-ai\wiki-ingest-brief.json` 和 reading report。

## 已知风险

- `docs/epi-linkage.md`、`docs/structure.md`、`docs/progress.md` 会增加 Plugin Eval 的 deferred token 估算，但这些文档是当前用户要求的维护材料，不应为了静态分数移出插件 docs。
- `paper-search` CLI、MinerU、Zotero 都是外部能力。缺失时应 warning 和引导，不应让只读诊断失败。
- `MINERU_TOKEN` 不得写入文档、日志、报告或配置预览，只能显示 set/missing。
- 当前安装 cache 不是开发源；源码提交并经 marketplace 升级后，安装副本才会变化。用户级 runtime.json 位于 `%USERPROFILE%\.codex\plugins\paper-search\epi\runtime.json`，不随 cache 版本目录替换。
- 最终 Obsidian/LLM Wiki 写入依赖目标 vault contract。EPI 只能提供 handoff 和 suggested routes，不能把固定脚本当成最终沉淀机制。
