# S3 设计：EPI/PRW 文档与契约 canonical 化 + 边界澄清

- **日期**：2026-06-07
- **状态**：设计待用户复审（spec self-review 已过）
- **所属 program**：EPI/PRW 跨平台 skill-based-architecture 迁移（S1 跨平台外壳/打包｜S2 skill 目录结构｜**S3 本文档**｜S4 EPI→PRW 主动续接提醒）。用户选择从 S3 起步。
- **审计来源**：`docs/audits/2026-06-07-epi-prw-optimization-audit.md`

## 1. 目标与非目标

**目标**：消除 EPI/PRW 文档与契约层的重复、漂移与自相矛盾，统一"谁写 wiki"的自我模型，并修两处机械问题。覆盖审计项 **A1–A5、C1–C4、E1、D3**。

**非目标（明确不在 S3）**：
- S1（`.claude-plugin/` 清单、`CLAUDE.md` 外壳、SessionStart hook、跨平台打包）。
- S2（每 skill `rules/` 目录化、PRW 根 `rules/` 归位、workflow 抽共享 reference、conformance.yaml）。
- S4（EPI→PRW 主动提醒）。
- 任何 Python 重构（D1/D2 单体拆分）——本轮只有 D3（删冗余别名）+ C2 的小常量改动。
- 不改任何运行链路语义；唯一的契约/行为变化是 **C2**（required→optional 技能栈）。

## 2. 已锁定决定（来自 brainstorm）

| 决定 | 取值 |
| --- | --- |
| C2 自我模型 | **PRW `$paper-research-wiki` = canonical 写入/维护层**；external obsidian-wiki skills = 可选 upstream 参考（PRW 已内化其模式，正常运行默认不调用） |
| C2 实现深度 | **(a) 全量**：含 `wiki_contracts.py` `REQUIRED_WIKI_SKILLS`→`OPTIONAL_WIKI_SKILLS` 迁移 + brief/gate 传播 + 测试 + 文档 |
| C3 只读问答归属 | 归 PRW `ask_wiki`（对话主入口）；EPI `wiki-ask` CLI 保留为 fallback/程序化入口；文档标注二者同源、对话优先 PRW；**不删代码** |
| C4 双 artifact | 仅文档/contract 层标 `wiki-ingest-brief.json`=canonical、`wiki_deposition_task.json`=deprecated（仍读兼容）；**本轮不动 Python** |
| A5 canonical 源 | page-family/frontmatter 的**人读 canonical** = PRW `rules/wiki-writing-standard.md`；EPI 文档与 PRW 其它文件改为指向它；代码强制常量（`wiki_contracts.py`）保留为执行层 |
| 兼容广度 | Claude + Codex（S1 落地，S3 内容平台中性，不与之冲突） |
| 版本 | EPI/PRW 同步 bump `0.2.0` → `0.2.1`；TDD，全测试套件保持绿 |

## 3. 目标端状态（S3 完成后）

- **`epi-linkage.md`** = pipeline 事实**唯一** canonical（保持现状，不瘦身；只更新 C2 相关的 `wiki_rule_source_model` 一节）。
- **`overview.zh.md`** = 纯导航层：保留"三层心智模型表 + artifact 速查 + 推荐阅读顺序"，删除逐阶段 artifact/命令重述，改为指向 `epi-linkage.md` 锚点。
- **`workflow.md`** = 安装后短入口：第 47、70 行的巨段拆成"命令清单 + 一句话职责 + 指向 epi-linkage 链接"；保留 easyscholar 契约提及（测试要求）。
- **doc map（权威分工）** = 只在 `epi-linkage.md` 顶部声明一处；`overview.zh.md`/`structure.md`/`progress.md`/`workflow.md` 顶部各保留一行指针。
- **`progress.md`** = 当前状态快照（定位/最近健康检查/已知风险/下一步）；历史逐轮变更与 file-list 迁出到新建的 `plugins/epi/docs/CHANGELOG.md`。
- **page-family/frontmatter canonical** = PRW `rules/wiki-writing-standard.md`；EPI 4 文档 + PRW `page-families.md`/`page-family-contract.md`/`formal-page-frontmatter.md` 改为指向它（保留 code 执行常量）。
- **`epi-paper-deposition`** = 薄 compatibility alias（SKILL≈20–25 行、`formal-wiki-write.md`≈15–20 行）：保留测试锚点（`formal-wiki-write.md`、`wiki_deposition_task.json`、`epi-wiki-deposition`、`$paper-research-wiki`、route `category: compatibility`），删除 external-stack runbook 与重复的 page-family/frontmatter/QMD 重述。
- **`REQUIRED_WIKI_SKILLS`** 仅含 `paper-research-wiki` + `epi-paper-deposition`；external（`llm-wiki`/`wiki-ingest`/`wiki-context-pack`/`wiki-lint`/`wiki-stage-commit`/`wiki-status`/`wiki-query`/`tag-taxonomy`）移入 `OPTIONAL_WIKI_SKILLS`。
- **只读问答**：EPI/PRW 文档明确 PRW `ask_wiki`=对话主入口、EPI `wiki-ask` CLI=fallback/程序化，二者同源。
- **`wiki_deposition_task.json`** 在 contract 文档中标 deprecated（canonical=`wiki-ingest-brief.json`），代码仍生成/读取。
- **EPI `plugin.json` `description`** 改为与 longDescription 一致的全链路定位。

## 4. 各项设计

### A1 — `overview.zh.md` 瘦成导航（低测试耦合）
`overview.zh.md` 不在 `test_current_docs.py` 读取列表，可自由重构。保留：一句话定位、三层心智模型表（行 29-39）、artifact 速查（行 422-433）、推荐阅读顺序（行 412-420）。删除：§工作流总链路 0-8 的逐阶段 artifact/命令重述（指向 `epi-linkage.md` §对应章节）。

### A2 — `workflow.md` 巨段拆短
第 47 行（acquire/identity/parse/staging/handoff/record 散文）与第 70 行（handoff/record/skill-stack 散文）拆为：命令清单（已有 powershell 块）+ 每命令一句话 + "完整语义见 `docs/epi-linkage.md` §N"。**必须保留** easyscholar 契约相关语句（`test_current_docs.py:258-261` 断言 workflow.md 含 easyscholar）。

### A3 — 单一 doc map
`epi-linkage.md` 顶部"配套文档"段落升级为唯一权威分工声明（保留现有 `docs/structure.md`/`docs/progress.md`/`docs/config.md` 指针，`test_current_docs.py:77-79` 要求）。`overview.zh.md:5-10`、`structure.md:3`、`progress.md:3` 的层级声明改为一行"权威分工见 `epi-linkage.md`"。

### A4 — `progress.md` 瘦身
保留 `test_current_docs.py:155` 要求的 status/verification/next-steps 段落 + "当前定位 + 最近一轮健康检查 + 已知风险"。把"本轮/上一轮变更范围 + file-list"（行 64-277）迁到新 `plugins/epi/docs/CHANGELOG.md`，progress.md 留一行指针。

### A5 — page-family/frontmatter canonical 指向
PRW `rules/wiki-writing-standard.md` 为人读 canonical。EPI `workflow.md`/`epi-linkage.md`/`structure.md`/`overview.zh.md` 中的"七类目录 + frontmatter 字段"列表保留**最小必要**（测试断言的）并加"完整 contract 见 PRW `rules/wiki-writing-standard.md`"。代码常量 `wiki_contracts.py:109 FORMAL_FRONTMATTER_REQUIRED_FIELDS` 等保留为执行层，加注释指明人读 canonical 位置。**风险**：S2 可能移动 PRW `rules/` 路径 → 届时更新这些 cross-ref（见 §7）。

### C1 — 折叠 `epi-paper-deposition` 为薄 alias
`SKILL.md`：保留 frontmatter + "本 skill 是 legacy `wiki_deposition_task.json`/`epi-wiki-deposition` 的 compatibility alias，一律路由到 PRW `$paper-research-wiki`" + 必需锚点 + bootstrap/QMD/page-family 边界**改为指向 canonical**（PRW wiki-writing-standard / wiki-provenance），删除自带的完整列表。`formal-wiki-write.md`：压成"加载 required inputs → 路由到 `$paper-research-wiki`"，删 external-stack runbook（行 22-39）与重复 frontmatter/page-family/QMD（行 43-111）。**更新** `test_skill_bundle_contract.py:403` 的"required adapter stack"断言为新模型。

### C2 — 统一"谁写 wiki"模型（含代码）
1. `wiki_contracts.py`：`REQUIRED_WIKI_SKILLS` 收为 `(paper-research-wiki, epi-paper-deposition)`；external 8 个移入 `OPTIONAL_WIKI_SKILLS`。
2. 传播：`stage_wiki.py`/`wiki_ingest_handoff.py`/`paper_gate.py` 中消费 `required_wiki_skills()` 的 brief/handoff/gate 字段随之变化；更新对应测试（`test_wiki_ingest_handoff.py`/`test_paper_gate.py`/`test_wiki_ingest_record.py`/`test_wiki_deposition_task.py`）。
3. 文档：`epi-linkage.md` §"Obsidian Wiki 规则来源模型" 简化——PRW 升为主执行层，external obsidian-wiki repos 标"可选 upstream 参考，PRW 已内化"；保留 `Ar9av/obsidian-wiki`/`kepano`/`obsidian-wiki-dev` 名称（`test_epi_linkage_doc.py:39-41` 断言存在）；**更新** `test_epi_linkage_doc.py:44-46` 关于 `wiki_rule_source_model` 的措辞断言。`workflow.md`/`structure.md`/`overview.zh.md` 的"required skill stack"同步改为"canonical=`$paper-research-wiki`，external 可选"。

### C3 — 只读问答归属（文档）
`epi-linkage.md`/`overview.zh.md`/`workflow.md` 的 `wiki-ask` 段 + PRW `ask-wiki.md`/`epi-integration.md` 标注：PRW `ask_wiki`=对话主入口，EPI `wiki-ask` CLI=同源的 fallback/程序化（`--json`）入口，互相指引。不改代码。

### C4 — `wiki_deposition_task.json` 文档标 deprecated
`epi-artifact-contract.md`、`epi-linkage.md`、`structure.md`、PRW `extract-papers.md`/`epi-integration.md`：声明 canonical=`wiki-ingest-brief.json`、`wiki_deposition_task.json`=deprecated（仍读兼容，迁移意图）。代码与相关测试不动。

### E1 — `plugin.json` description
`plugins/epi/.codex-plugin/plugin.json:4` `description` 改为全链路定位（与 `longDescription` 一致的精简版）。检查 `test_marketplace_manifest.py` 是否断言该字段。

### D3 — 删 `_write_json` 别名
`orchestrator.py:91` 删 `_write_json`，全部 `_write_json` 调用点改为直接 `write_json_atomic`（已核实语义等价；精确计数 plan 阶段定，grep 显示 `_write_json`/`write_json_atomic` 合计约 30 处）。全测试保持绿。

## 5. 测试与版本影响

| 类别 | 文件 | 动作 |
| --- | --- | --- |
| 必须保持绿（内容保留） | `test_current_docs.py`（epi-linkage 指针/discovery refs/progress 段/workflow easyscholar）、`test_wiki_deposition_task.py` 等（C4 不动码） | 保留被断言内容 |
| 需更新断言（有意变化） | `test_epi_linkage_doc.py:44-46`（C2 wording）、`test_skill_bundle_contract.py:403`（C1 stack）、`wiki_contracts` 消费方测试（C2 brief/gate/handoff/record） | TDD 先改测试表达新契约，再改实现 |
| 需核查 | `test_marketplace_manifest.py`（E1）、`tests/paper_research_wiki/test_plugin_contract.py`（A5/C3/C4 PRW 文档断言） | plan 阶段逐条对账 |

版本：EPI/PRW `plugin.json` 同 bump `0.2.1`；`docs/progress.md`/`CHANGELOG.md` 记录本轮；安装 cache 仍需 marketplace refresh（不在 S3）。

## 6. S3 内部实施顺序（plan 将细化）
1. **快速赢**：E1 → D3 → C4（纯文档标注）。
2. **契约（含码）**：C2（先改 `test_*` 表达新契约 → 改 `wiki_contracts.py` + 传播 → 绿）→ C1（薄化 + 更新 bundle 断言）。
3. **文档 canonical 化**：A3（doc map）→ A1（overview 瘦身）→ A2（workflow 拆段）→ A4（progress 瘦身 + CHANGELOG）→ A5（page-family/frontmatter 指向）。

## 7. 风险与缓解
- **S2 路径迁移**：A5/C1 指向 PRW `rules/wiki-writing-standard.md`；S2 若把 PRW `rules/` 移入 `skills/<name>/rules/` 或 `skills/shared/`，需在 S2 内更新这些 cross-ref。缓解：S3 用当前路径，S2 plan 显式列入"更新 S3 建立的 cross-ref"。
- **文档断言脆性**：A1/A2/A3 重构易碰 `test_current_docs.py` 断言。缓解：plan 先 `pytest tests/epi/test_current_docs.py tests/epi/test_epi_linkage_doc.py` 跑出当前绿，逐文件改后即跑。
- **C2 跨码/文档一致性**：必须同一 PR 内改 `wiki_contracts.py` + brief/gate + 文档 + 测试，避免 doc↔brief 不一致（这正是选 (a) 深度的原因）。

## 8. 验收
- `pytest tests/epi tests/paper_research_wiki plugins/epi/tests -q` 全绿。
- EPI/PRW plugin validation 通过；`plugin.json` 版本=`0.2.1`。
- 抽查：`epi-linkage.md` 仍含 `test_epi_linkage_doc.py` 要求的事实；`overview.zh.md` 无逐阶段重述；`workflow.md` 无 >300 字巨段；`REQUIRED_WIKI_SKILLS` 仅 2 项；`epi-paper-deposition` 两文件均 ≤25 行且保留锚点；EPI `plugin.json.description` 全链路化。
- doc↔code 一致：生成的 `wiki-ingest-brief.json` required skills 与文档表述一致。

## 9. 交接到后续 spec
- S1：消费 S3 已 canonical 化的 docs/contract 撰写 `CLAUDE.md`/`AGENTS.md` 外壳的 routing bootstrap 与 Always-Read 指针。
- S2：把 PRW 根 `rules/` 与每 skill `rules/` 结构化，更新 S3 建立的 cross-ref。
- S4：基于 C2（PRW canonical）模型，让 EPI handoff 输出显式 PRW 续接话术。
