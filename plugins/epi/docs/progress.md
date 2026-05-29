# EPI 插件进度说明

更新时间：2026-05-30。本文档记录当前源码树的开发状态、已完成能力、已知风险和下一步计划。它是面向继续开发和发布验收的进度页，不替代 `docs/epi-linkage.md` 的链路契约，也不替代 `docs/structure.md` 的结构说明。

## 当前定位

EPI 当前聚焦“高质量论文收集和整理 -> Obsidian/LLM Wiki 知识沉淀 -> 轻阅读负担报告”。它不是自动完成选题、实验、写作、投稿的科研工作台。复现思路可以出现，但只作为阅读报告中的 compact caveat 和验证线索，不占主要篇幅。

## 已完成能力

- Marketplace 包装：`plugin.json` 已声明 EPI 展示信息、GitHub marketplace 链接、技能目录和默认提示。
- 安装诊断：`doctor` 支持只读健康检查，区分插件结构错误和外部依赖 warning，并能给 `paper-search` 与 MinerU 配置链接。
- 配置引导：`config-status`、`init-config`、`propose-config-update`、`apply-config-update` 已形成配置生命周期；当前新增 `config-setup` skill，把首次配置和修改配置改成聊天式逐步引导。
- 论文发现：`dry-run` 支持候选标准化、过滤、ranking、报告、run index 和 research queue，且只写 `_runs`。
- 推进采集：`advance-ranked`、`advance-paper`、`advance-batch`、`ingest-one` 支持从候选论文进入 raw artifact、MinerU 解析、reader、critic 和 staging。
- Reader v2：已拆出三角色阅读输出、evidence map、证据地址校验和轻阅读报告所需摘要。
- Critic 质量门：`paper-quality-critic` 已从文件存在检查升级为工程论文可靠性检查，覆盖身份、claim support、benchmark integrity、复现信息 warning、scope overclaim 和 parse-vs-paper failure。
- Role critic quorum：Nature/Sci editor、peer reviewer、senior domain researcher 的角色审查已经进入 critic quorum 和后续 decision。
- Staging 和报告：通过 critic 后生成 suggested routes、`wiki-ingest-brief.json`、`promotion-plan.json` 和 `reports/<slug>-reading-report.md`。
- Agent-mediated wiki ingest：默认不由固定脚本写最终 wiki，而是生成 `wiki-ingest-handoff`，要求 agent 读取目标 vault contract 后再写入。
- Paper gate：`paper-gate` 提供 GitHub checks 风格只读质量门；`research-queue --actions` 以当前 gate 为准推荐下一步。
- Legacy promotion：`promote-to-wiki` 和 `rollback-promotion` 只保留旧 compiled-draft 路径，带路径安全限制和人工确认。
- Self-evolution：`propose-evolution`、`activate-evolution`、`evolution-query` 已采用 proposal-based、human approval、validation gate 和 metric comparison。
- 查询与维护：`runs-query`、`research-queue`、`wiki-query` 支持状态查询；redo/recritic 支持阶段性修复但不绕过 critic gate。

## 当前未提交工作

当前源码树还有配置引导相关未提交改动，范围集中在：

- `plugins/epi/skills/config-setup/SKILL.md`
- `plugins/epi/docs/config.md`
- `plugins/epi/docs/epi-linkage.md`
- `plugins/epi/docs/structure.md`
- `plugins/epi/docs/progress.md`
- `plugins/epi/.codex-plugin/plugin.json`
- 现有 EPI skill 中对 `config-setup` 和 `docs\config.md` 的引用
- `tests/epi/test_config_onboarding_docs.py`

这些改动的目标是：当用户首次使用时，如果本机还没有配置 `paper-search` CLI、`MINERU_TOKEN` 或 `_meta\epi-config.yaml`，EPI 不直接启动论文流程，而是通过 `config-setup` 用自然语言逐步引导，并提供必要链接。

## 最近验证

本轮已验证：

```powershell
python -m pytest tests\epi\test_config_onboarding_docs.py -q --basetemp .pytest_tmp_handoff_config
```

结果：`3 passed in 0.21s`。

上一轮开发摘要记录过更大范围结果：`tests\epi plugins\epi` 通过、EPI 插件 validation 通过、Plugin Eval 达到 `91/100` 且 `0 fail, 2 warn`。这些结果在当前配置引导改动后尚未本轮重跑，因此发布前必须重新验证。

## 发布前必须重跑

```powershell
python -m pytest tests\epi -q --basetemp .pytest_tmp_epi_current
python C:\Users\liuchf\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py D:\paper-search\plugins\epi
python C:\Users\liuchf\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py D:\paper-search\plugins\mineru-paper-parser
python -m coverage run -m pytest tests\epi
python -m coverage xml -o plugins\epi\coverage\coverage.xml
node C:\Users\liuchf\.codex\plugins\cache\openai-curated\plugin-eval\719ed655\scripts\plugin-eval.js analyze D:\paper-search\plugins\epi --format markdown
```

验收标准：

- 源码测试通过。
- 两个插件 validation 通过。
- Plugin Eval 无 fail，分数不低于 `70/100`。
- coverage artifact 可被 Plugin Eval 识别。
- 若仍有 Windows `py-tests-missing` warning，需记录为评估器路径识别限制，而不是删除源码测试。

## 下一步计划

1. 完成当前配置引导文档和 `config-setup` skill 的审查，确认 `plugin.json` 的版本 bump 是发布意图而不是误改。
2. 跑文档/配置相关测试，再跑完整 `tests\epi`。
3. 跑 EPI 与 MinerU 插件 validation。
4. 将配置引导、结构文档和进度文档作为一个 scoped commit 提交。
5. 需要发布时刷新 coverage 和 Plugin Eval，并推送 GitHub，让 Codex marketplace 从 `main` 升级。
6. 升级安装副本后，从新 Codex thread 用 `@epi` 运行 `doctor --json`、`config-status --json`、dry-run fixture smoke 和 `research-queue` 验证安装体验。

## 已知风险

- `docs/epi-linkage.md`、`docs/structure.md`、`docs/progress.md` 会增加 Plugin Eval 的 deferred token 估算，但这些文档是当前用户要求的维护材料，不应为了静态分数移出插件 docs。
- `paper-search` CLI、MinerU、Zotero 都是外部能力。缺失时应 warning 和引导，不应让只读诊断失败。
- `MINERU_TOKEN` 不得写入文档、日志、报告或配置预览，只能显示 set/missing。
- 当前安装 cache 不是开发源；源码提交并经 marketplace 升级后，安装副本才会变化。
- 最终 Obsidian/LLM Wiki 写入依赖目标 vault contract。EPI 只能提供 handoff 和 suggested routes，不能把固定脚本当成最终沉淀机制。

