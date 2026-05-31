# EPI 插件进度说明

更新时间：2026-05-31。本文档记录当前源码树的开发状态、已完成能力、已知风险和下一步计划。它是面向继续开发和发布验收的进度页，不替代 `docs/epi-linkage.md` 的链路契约，也不替代 `docs/structure.md` 的结构说明。

## 当前定位

EPI 当前聚焦“按用户画像/config 衍生的高质量论文收集和整理 -> Obsidian/LLM Wiki 知识沉淀 -> 轻阅读负担报告”。它是通用学术论文插件，不默认任何学科方向；AUV、机器人、AI、医学等词只能来自用户配置、当前请求或显式领域 hint。它不是自动完成选题、实验、写作、投稿的科研工作台。复现思路可以出现，但只作为阅读报告中的 compact caveat 和验证线索，不占主要篇幅。

## 已完成能力

- Marketplace 包装：`plugin.json` 已声明 EPI 展示信息、GitHub marketplace 链接、技能目录和默认提示；展示文案已从单一工程/机器人方向改成通用 academic/profile-driven 定位。
- 安装诊断：`doctor` 支持只读健康检查，区分插件结构错误和外部依赖 warning，并能给 `paper-search` 与 MinerU 配置链接。
- Runtime 配置：新增 `runtime_config.py`，从 `%USERPROFILE%\.codex\plugins\paper-search\epi\runtime.json` 自动加载 `paper-search` MCP、CLI fallback 和 MinerU env-file 路径；显式 env 优先，runtime.json 不保存 token 明文。
- Marketplace polish：`defaultPrompt` 已压到 3 条，避免 Codex 只使用前三条时丢失后续提示。
- 配置引导：`config-status`、`init-config`、`propose-config-update`、`apply-config-update` 已形成配置生命周期；当前新增 `config-setup` skill，把首次配置和修改配置改成聊天式逐步引导。
- Wiki 初始化：新增 `wiki-setup` skill，专门负责 paper research wiki vault 初始化和重置；初始化幂等补结构，重置必须盘点、备份计划和二次确认。已修正 reset 坑点并落到 CLI：`wiki-reset --preview` 可先列出影响路径，`wiki-reset` 默认重置 wiki 内容时保留 `_meta\epi-config.yaml`、`_meta\epi-config-state.json`、config history 和用户级 runtime.json；只有用户额外确认 `确认同时重置 EPI config` 并传入 `--reset-config-confirmed-by` 才允许删除或重置配置。若发现误删、误操作或 config 意外缺失，skill 会停止后续论文流程，先用 `wiki-repair` 单入口检查，或用 `config-recover` 搜索 reset backups、config history 和 runtime.json 相关恢复线索，再用 `config-restore` 在确认后恢复。
- 论文发现：`dry-run` 支持候选标准化、过滤、ranking、报告、run index 和 research queue，且只写 `_runs`。
- 发现输出：`paper-discovery` skill 已要求对话中先给“推荐优先看”清单，再给 EPI 实测证据；清单要包含本轮找到且保留下来的全部候选论文，并按阅读优先级排序。每篇推荐包含 venue/year、DOI、引用数、影响因子/分区或未核实、venue prior、PDF/代码可用性、方法场景、验证证据和 caveat。用户明确不要综述时，查询和 filter 会硬排除 review/survey 类结果。高质量检索新增 topic blocks、3-5 个 focused query variants、source routing、DOI/title 去重、wiki 已下载库去重、venue prior、Tier A/B/C 质量门控和 recall gap 记录，避免把 MCP 返回结果本身当成质量定义。
- 论文发现 skill bundle：`paper-discovery` 已蒸馏 `nature-academic-search` 的结构化组织方式，新增中文 README、离线 query planner、domain ontology、source tier、dedup engine、venue prior、two-stage retrieval、citation graph、evaluation set、multi-source workflow 等分层参考文件；venue prior 现在明确是用户画像/config 驱动，领域 curated list 只能作为对应用户领域的 prior，论坛/社区榜单只能作为弱召回线索，影响因子、分区、引用数等仍需实时或可信来源核验。
- 精准检索计划：`skills/paper-discovery/scripts/query-planner.py` 可把用户画像/config 和用户主题转换成 `query_plan`，包含 profile、概念块、`domain_focus_terms`、5-8 条 query variants、source route、recall gap checks 和 quality signals；默认 `dry-run` 已接入 query plan，会写 `query-plan.json`，按 query variants 多次搜索并合并 candidate pool；`dry-run --json` 可打印 run id 和关键 artifact 路径，方便 agent 串联；默认排除 review/survey/meta 类综述候选，用户明确找综述时才放开。EPI 不再把 AUV/机器人/AI 等词作为全局默认，而是从 `_meta\epi-config.yaml` 的 profile、domains、positive_keywords、negative_keywords、venue_prior 和当前请求衍生检索词；query plan 的扩展词只用于召回，`domain_focus_terms` 才是 narrow topic 的硬锚点，ranking 的画像匹配词使用用户 config 和当前请求核心词，避免宽召回词稀释窄主题相关性；若 profile-derived 计划偏离当前请求，使用 `--no-query-plan` 精确短语查询或先更新 config。
- 1-3 快路：`prepare-ranked` 支持从 dry-run 的 `rank.json` 直接完成 selected ranked paper acquire + MinerU parse，并停在 raw artifact，不误入 reader/critic/staging。实测批量用 `--max-papers 10 --skip-existing`，补跑时已解析论文不占预算；`--max-papers 1` 只作为 smoke test；`--json` 会输出 prepared run id、source run id、processed/skipped counts、`stops_after=parse` 和关键 report artifact 路径，方便 agent 串联。单篇下载/解析异常会记录为该论文的失败状态并继续后续候选。
- 推进采集：`advance-ranked`、`advance-paper`、`advance-batch`、`ingest-one` 支持从候选论文进入 raw artifact、MinerU 解析、reader、critic 和 staging。
- MinerU 产物整理：成功解析后最终产物只保留在 `mineru/`，大型 `mineru-command/paper` 与 `mineru-command/parsed` 工作副本会清理；若 MinerU 没有原生 TeX，生成非空 Markdown-derived LaTeX fallback 并记录 `tex_source`。若 MinerU stdout 显示任务 done 但没有 Markdown，错误会明确记录为 `MinerU reported done but produced no Markdown output` 并保留工作目录用于诊断。
- Reader v2：已拆出三角色阅读输出、evidence map、证据地址校验和轻阅读报告所需摘要。
- Critic 质量门：`paper-quality-critic` 已从文件存在检查升级为学术论文可靠性检查，覆盖身份、claim support、benchmark integrity、复现信息 warning、scope overclaim 和 parse-vs-paper failure。
- Role critic quorum：Nature/Sci editor、peer reviewer、senior domain researcher 的角色审查已经进入 critic quorum 和后续 decision。
- Staging 和报告：通过 critic 后生成 suggested routes、`wiki-ingest-brief.json`、`promotion-plan.json` 和 `reports/<slug>-reading-report.md`。
- Agent-mediated wiki ingest：默认不由固定脚本写最终 wiki，而是生成 `wiki-ingest-handoff`，要求 agent 读取目标 vault contract 后再写入。
- Paper gate：`paper-gate` 提供 GitHub checks 风格只读质量门；`research-queue --actions` 以当前 gate 为准推荐下一步。
- Legacy promotion：`promote-to-wiki` 和 `rollback-promotion` 只保留旧 compiled-draft 路径，带路径安全限制和人工确认。
- Self-evolution：`propose-evolution`、`activate-evolution`、`evolution-query` 已采用 proposal-based、human approval、validation gate 和 metric comparison。
- 查询与维护：`runs-query`、`research-queue`、`wiki-query` 支持状态查询；redo/recritic 支持阶段性修复但不绕过 critic gate。
- 过渡态生命周期：`run-lifecycle` 支持 `_runs` 单次 run 目录 dry-run/apply 清理，保留面板文件并写 `_meta/run-lifecycle` manifest；EPI run 结束后会自动检查 `_runs`，超过 15 个单次 run 目录时自动应用 cleanup，保留最新 15 个 terminal run 并按 workflow 至少保留 2 个；发现阶段会和 `_raw/papers` 已下载论文按 DOI/arXiv/title 去重，避免重复推荐。

## 本轮相关变更范围

本轮新增修复集中在插件 cache 环境不继承手工 `.env`、完整链路实测和 1-3 raw preparation 暴露的问题：

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
- `plugins/epi/skills/paper-discovery/README.md`
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
- 失败点：安装版 `0.1.0+codex.20260531111632` 实测 AUV/RL/control 非综述查询时，`not review` 只触发 review 排除，没有连带排除 survey/meta；部分 `A Survey...`、`surveys recent advances` 和泛 autonomous vehicles 结果进入 `rank.json`。修复：显式非综述请求统一使用完整 review/survey/meta 文档类型排除；源码版复测 run `20260531T034732053575Z` 中 `rank.json` 从 60 个 raw candidates 收敛到 3 个 AUV/control 相关候选，Survey/Review、Blockchain autonomous vehicles、泛 RL 均进入 rejected。
- 失败点：`run-lifecycle` 只有手动命令和 skill，没有被主链路自动接管；默认 `keep-latest=30` 时用户实测 `_runs` 已堆到 17 个目录仍不会清理。修复：默认 `keep-latest=15`，并在 dry-run / batch advance / prepare-ranked 结束后自动检查和应用 lifecycle cleanup，仍只删除 `_runs` 下 terminal 单次 run 目录，不碰 dashboard/index、`_raw`、`_staging`、配置或 Zotero。
- 失败点：安装版 `prepare-ranked` 没有 `--json`，实测后续只能解析文本输出，降低 agent 自动跟踪稳定性。修复：为 `prepare-ranked` 增加机器可读 JSON 输出，并同步 workflow 与 paper-discovery/paper-ingest skill。
- 失败点：出版社 PDF 403/502 被误解为“没有论文”。修复：skill 将其标为 acquisition evidence，并要求尝试开放来源或 arXiv-first rerun。
- 失败点：MinerU stdout 显示 done 但无 Markdown 时错误过泛。修复：记录明确错误文本和 batch id。

## 最近验证

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

结果：最新相关回归为 `26 passed in 1.43s`；最新全量 `tests\epi` 为 `268 passed in 29.24s`；EPI plugin validation passed；插件包未发现本机绝对路径泄漏。历史 coverage run 为 `211 passed in 19.92s`，`plugins\epi\coverage\coverage.xml` 已刷新；历史 Plugin Eval 结果为 `82/100`、`0 fail, 4 warn`、coverage `93.49%`；remaining warnings 为 token budget 和 Windows 路径下 `py-tests-missing` 识别限制。

1-3 真实目录整理结果如下。这是历史实测样例，不代表 EPI 的默认研究方向：

- 论文 raw root：`<vault>\_raw\papers\a-survey-learning-embodied-intelligence-from-physical-simulators-and-world-models`。
- `mineru\paper.md`：`330048` bytes。
- `mineru\paper.tex`：`336909` bytes，`tex_source=markdown-fallback`。
- `mineru\images`：`68` files。
- `work_dir_retention=logs-only`。
- `mineru-command\paper` 与 `mineru-command\parsed` 已清理，只保留 stdout/stderr 日志。

真实链路实测结果：

- 发现 run：`<vault>\_runs\20260529T191647886910Z`，MCP 优先调用，MCP 返回 0 篇后记录 fallback，CLI fallback 找到 `A Survey on Robotics with Foundation Models: toward Embodied AI`。
- 论文 raw root：`<vault>\_raw\papers\a-survey-on-robotics-with-foundation-models-toward-embodied-ai`。
- 修复前状态：`critic_failed`，阻断项为 `benchmark_integrity`。
- 修复后 `recritic`：`critic-quorum.json` 六个 reviewer 全部 pass，`paper-quality-critic` 记录 `benchmark_integrity: no explicit outperform/SOTA claim detected`。
- `advance-paper` 后状态：`staged`，`next_action=run-wiki-ingest-agent`。
- `paper-gate --json`：`status=waiting_for_human_gate`，`failure_checks=[]`，仅 `human-approval` action required。
- `wiki-ingest-handoff --json`：`ready_for_agent=true`，handoff artifacts 位于 `_staging\papers\<slug>`。

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
4. 记录 human approval 后，交给 wiki-ingest agent 消费 `_staging\papers\a-survey-on-robotics-with-foundation-models-toward-embodied-ai\wiki-ingest-brief.json` 和 reading report。

## 已知风险

- `docs/epi-linkage.md`、`docs/structure.md`、`docs/progress.md` 会增加 Plugin Eval 的 deferred token 估算，但这些文档是当前用户要求的维护材料，不应为了静态分数移出插件 docs。
- `paper-search` CLI、MinerU、Zotero 都是外部能力。缺失时应 warning 和引导，不应让只读诊断失败。
- `MINERU_TOKEN` 不得写入文档、日志、报告或配置预览，只能显示 set/missing。
- 当前安装 cache 不是开发源；源码提交并经 marketplace 升级后，安装副本才会变化。用户级 runtime.json 位于 `%USERPROFILE%\.codex\plugins\paper-search\epi\runtime.json`，不随 cache 版本目录替换。
- 最终 Obsidian/LLM Wiki 写入依赖目标 vault contract。EPI 只能提供 handoff 和 suggested routes，不能把固定脚本当成最终沉淀机制。
