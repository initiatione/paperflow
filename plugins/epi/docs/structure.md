# EPI 插件结构说明

本文档描述当前 EPI 插件的源代码结构、运行边界和主要产物位置。它回答“文件在哪里、谁负责什么、哪些目录不能被当成最终知识库写入入口”。端到端行为契约仍以 `docs/epi-linkage.md` 为准。

## 总体边界

EPI 是 Codex 插件源码包，位于 `<plugin-root>`。插件的目标链路是：高质量论文发现和排序 -> raw artifact 留痕 -> Reader/Critic 证据审查 -> staging evidence package -> wiki-ingest handoff -> 由 agent 按目标 Obsidian/LLM Wiki vault contract 写入最终知识库。

EPI 自身不应该把最终 Obsidian 页面路径、标签、合并策略或 staged writes 固定死。最终写入规则来自目标 vault 的 `AGENTS.md` 和 `_meta/*`，并参考个性化 `obsidian-wiki-dev`、`Ar9av/obsidian-wiki`、`kepano/obsidian-skills`。本插件只准备证据、报告、候选草稿和 handoff。

## 插件包目录

```text
plugins/epi/
  .codex-plugin/plugin.json
  docs/
  scripts/
  skills/
  templates/
  coverage/
```

- `.codex-plugin/plugin.json`：Codex marketplace 识别入口，包含插件名称、版本、展示文案、技能目录和 marketplace 链接。安装刷新通常需要更新版本 cachebuster。
- `docs/`：用户可读说明。`epi-linkage.md` 是主链路维护契约；`structure.md` 是本文件；`progress.md` 是开发进度说明；`config.md` 是首次配置和修改配置的话术来源。
- `scripts/`：Codex 插件内的可执行 wrapper。用户和技能通常调用 `python scripts\orchestrator.py ...`。
- `scripts/build/epi/`：实际 Python 实现模块。wrapper 会把这里作为包代码运行。
- `skills/`：Codex skills。每个 skill 的 `SKILL.md` 只保留触发条件、安全边界和核心命令，详细链路放在 docs。
- `templates/`：ranking、filter、interest、routing、critic checklist 示例。skill-aware evolution 只能在白名单和验证通过后提出或应用有限变更。
- `coverage/`：本地 coverage artifact 位置。`coverage.xml` 通常被 git ignore，只在发布评估需要时刷新或强制加入。

## CLI 入口

主入口是：

```powershell
python scripts\orchestrator.py <command>
```

当前命令分组：

- 安装与配置：`doctor`、`config-status`、`init-config`、`propose-config-update`、`apply-config-update`。
- Wiki 库初始化/重置：`wiki-setup` skill 负责初始化和重置流程；初始化只补缺失结构，重置必须先盘点、备份计划并要求用户二次确认 `确认重置 EPI wiki`。Wiki 结构重置和 EPI config 重置是两个操作；默认重置必须保留 `_meta\epi-config.yaml`、`_meta\epi-config-state.json`、config history 目录，并且不得触碰用户级 `%USERPROFILE%\.codex\plugins\paper-search\epi\runtime.json`。如需同时重置配置，必须另行确认 `确认同时重置 EPI config`。若出现误删或误操作，先停止后续论文流程，主动询问是否从备份/历史恢复重要设置。
- 发现与推进：`dry-run`、`advance-ranked`、`advance-paper`、`advance-batch`、`ingest-one`、`acquire-paper`。
- 解析与修复：`parse-paper`、`redo-acquire`、`redo-parse`、`redo-read`、`recritic`。
- Reader/Critic/Gate：推进命令内部生成 reader 和 critic；只读检查用 `paper-gate`。
- Staging 与 Wiki handoff：`wiki-ingest-handoff` 渲染 agent-mediated handoff；`promote-to-wiki` 仅保留 legacy compiled-draft 兼容。
- 索引与查询：`runs-query`、`research-queue`、`wiki-query`。
- 反馈与进化：`record-feedback`、`propose-evolution`、`activate-evolution`、`evolution-query`。
- 外部集成：`zotero-sync`，以及 MinerU 解析相关命令。

## Python 模块职责

```text
scripts/build/epi/
  cli.py
  orchestrator.py
  config.py
  doctor.py
  runtime_config.py
  paper_search_adapter.py
  normalize_candidates.py
  filter_candidates.py
  rank_papers.py
  acquire_papers.py
  run_mineru_parse.py
  generate_reader.py
  reader_*.py
  run_critic.py
  paper_quality.py
  role_critics.py
  research_decision.py
  reproduction_plan.py
  reader_revision_*.py
  stage_wiki.py
  paper_gate.py
  wiki_ingest_handoff.py
  promote_to_wiki.py
  run_index.py
  wiki_query.py
  skill_aware_evolve.py
```

- `cli.py` 只负责参数解析、JSON/Markdown 输出和调度到内部模块。
- `orchestrator.py` 是兼容入口和流程编排层，负责 dry-run、one-paper ingest、batch advance、redo/recritic 等阶段串联。
- `config.py` 负责 `_meta/epi-config.yaml` 的读取、初始化、提案和更新历史；配置缺失时必须走聊天式 `config-setup`。
- `doctor.py` 负责只读健康检查；外部依赖缺失是 warning，插件结构缺失才 error。
- `runtime_config.py` 负责从 `%USERPROFILE%\.codex\plugins\paper-search\epi\runtime.json` 加载本机依赖配置，只补缺失的进程环境变量，不覆盖显式 env，不保存 token 明文。
- `paper_search_adapter.py` 优先调用外部 `paper-search-mcp` stdio server，并在失败、超时或空结果时回退到 `paper-search` CLI，把上游输出标准化为 EPI 候选记录。
- `rank_papers.py` 负责 ranking signals、ranking protocol 和三角色排序解释。
- `run_mineru_parse.py` 负责 MinerU 命令调用、失败记录和 fixture materialization。
- `generate_reader.py`、`reader_outputs.py`、`reader_evidence.py`、`reader_protocol.py` 负责多角色 reader、evidence map 和证据地址校验。
- `run_critic.py`、`paper_quality.py`、`role_critics.py` 负责 critic quorum、工程论文可靠性检查和三角色质量门。
- `research_decision.py`、`reader_revision_plan.py`、`reader_revision_guidance.py`、`reproduction_plan.py` 把 critic 结果翻译成决策、修复建议和紧凑复现 caveat。
- `stage_wiki.py` 负责 `_staging` 草稿、轻阅读报告、`wiki-ingest-brief.json` 和 `promotion-plan.json`。
- `paper_gate.py` 是只读质量门面板，决定当前 slug 是 failure、waiting for human gate，还是允许进入下一动作。
- `wiki_ingest_handoff.py` 是只读 handoff 渲染器，给最终 wiki ingest agent 提供路径、规则优先级和 checklist。
- `promote_to_wiki.py` 只保留 legacy compiled-draft promotion 和 rollback，不能替代 agent-mediated wiki ingest。
- `run_index.py` 负责 `_runs/index.json`、dashboard 和 `research-queue.json`，并在 ready queue 里嵌入当前 paper-gate 摘要。
- `wiki_query.py` 只查询 legacy manifest/index 视角，不能代表目标 vault 的全部知识图谱。
- `skill_aware_evolve.py` 负责 proposal-based 自进化，默认不直接修改插件代码、用户配置或 compiled wiki。

## Skills 结构

```text
skills/
  config-setup/
  paper-discovery/
  paper-ingest/
  mineru-paper-parser/
  skill-aware-evolve/
  zotero-sync/
```

- `config-setup`：首次使用或修改配置时的唯一交互入口。一次只问一个问题；最终确认前不运行 `init-config` 或 `apply-config-update`。
- `paper-discovery`：搜索、排序和 dry-run；当用户要求“1-3”时，指向 `prepare-ranked` 快路，只写 raw 采集和 MinerU 解析产物。
- `paper-ingest`：推进已选论文进入 raw、reader、critic、staging 和 handoff。只需 1-3 时使用 `prepare-ranked`，不要误入完整 reader/critic/staging 链。
- `mineru-paper-parser`：低层 PDF -> Markdown/TeX/images/manifest 解析能力；成功后最终产物只放在 `mineru/`，`paper.tex` 必须非空，必要时使用 Markdown fallback。
- `skill-aware-evolve`：根据 evidence 和验证结果提出受控变更；配置问题必须走配置 proposal。
- `zotero-sync`：Zotero 记录和可选同步，默认安全边界是本地记录优先。

## Vault Artifact 结构

EPI 默认 vault 形态：

```text
<vault>/
  _meta/
    epi-config.yaml
    epi-config-state.json
    epi-config-history/
    config-history/
  _runs/
    <run-id>/
      normalized.json
      rank.json
      report.md
    index.json
    research-queue.json
  _raw/
    papers/<slug>/
      paper.pdf
      metadata.json
      acquire-record.json
      mineru/
      reader/
      critic/
      run-state.json
  _staging/
    papers/<slug>/
      references/
      concepts/
      synthesis/
      reports/
      wiki-ingest-brief.json
      promotion-plan.json
```

写入边界：

- `dry-run` 只写 `_runs`。
- raw 阶段写 `_raw/papers/<slug>`，不写 `_staging` 或最终 wiki。
- critic pass 后才允许写 `_staging/papers/<slug>`。
- `wiki-ingest-handoff` 和 `paper-gate` 都是只读。
- 当前默认 agent-mediated plan 不写 compiled wiki。
- legacy `promote-to-wiki` 只处理显式 compiled targets，并要求 `approved-by`。

## 测试与发布结构

源码测试主要在宿主仓库的 `tests\epi`。插件内 wrapper smoke 由源码测试覆盖，避免在插件包内放重复测试文件增加 token budget。

常用检查：

```powershell
python -m pytest tests\epi -q
python -m pytest tests\epi tests\epi\test_wrapper_entrypoints.py -q
python <plugin-creator-validate-script> <plugin-root>
node <plugin-eval.js> analyze <plugin-root> --format markdown
```

安装副本在 `%USERPROFILE%\.codex\plugins\cache\paper-search\epi\<version>`。源码改动必须先提交并通过 GitHub/marketplace 升级流程进入安装副本；不要把安装 cache 当成开发源。

用户级 runtime 配置不放在安装 cache 版本目录，而放在 `%USERPROFILE%\.codex\plugins\paper-search\epi\runtime.json`，用于保存 MCP/CLI/MinerU 命令路径和 `mineru.env` 路径；插件升级 cache 不应覆盖它。
