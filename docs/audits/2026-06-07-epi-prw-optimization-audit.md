# EPI / PRW 插件优化审计（2026-06-07）

## 范围与方法

本审计回应"找到 EPI 与 PRW 两个插件工作流程/工作效果待优化处，以及编写形式问题"的请求。三项前置决定（用户确认）：

1. **产出**：先给优先级审计（本文件），用户挑选后再逐项 `brainstorm → spec → 实现`。
2. **优先轴**：以**编写形式 / 可维护性**为主，工作流效果/自动化缺口列全但排后。
3. **边界**：遇到 EPI/PRW 职责重叠时，**允许提议重新划边界**（不限于"只去重"）。

**已审阅**：两个 `plugin.json`、两个 `AGENTS.md`、两个 `routing.yaml`、README、marketplace.json；EPI `docs/{workflow,epi-linkage,structure,overview.zh,progress}.md`；PRW 全部 5 个 workflow、4 个 rule、关键 reference、`epi-integration.md`；`epi-paper-deposition` skill + `formal-wiki-write.md`；Python 模块的规模/结构（`grep` 函数计数 + `structure.md` 的模块职责表）。

**未深读（结论按推断标注，需要时再确认）**：`references-page-anatomy.md`(356 行)、`config.md`/`evaluation.md`/`recovery.md`/`attribution.md`、`paper-wiki-language/SKILL.md` + `style-guide.md`、各 Python 模块逐行实现。Python 部分的发现基于**规模 + 结构 + 自带文档**，足以支撑"单体"判断，但具体拆分边界落地时仍需逐函数确认。

## 图例

- 严重度：**P1**=高（持续制造漂移/不一致，维护税最重）｜**P2**=中（明显冗余或单体，改动有收益但风险/工作量较大）｜**P3**=低/快速赢（便宜、低风险）。
- 轴：**FORM**=编写形式/可维护性（本轮重点）｜**BNDRY**=跨插件边界（触及 Q3）｜**EFFECT**=工作流效果/自动化（本轮次要）。

## 优先级汇总表

| ID | 轴 | 严重度 | 一句话 | 关键证据 |
| --- | --- | --- | --- | --- |
| A1 | FORM | P1 | EPI 完整 pipeline 在 4 个中文文档各讲一遍（~1117 行） | epi-linkage §主链路1-9；overview.zh §0-8；structure；workflow.md:47,70 |
| A2 | FORM | P1 | `workflow.md` 违反自身"短入口"定位，含 700-1000 字 runbook 巨段 | workflow.md:47,70 vs epi-linkage:15 / overview:9 |
| A3 | FORM | P2 | canonical 文档层级在 4 处各自声明、措辞不一 | epi-linkage:5-15；overview:5-10；structure:3；progress:3 |
| A4 | FORM | P3 | `progress.md`(447) 是 append-only changelog + 每轮 file-list（git 的活） | progress.md:64-277 |
| A5 | FORM/BNDRY | P2 | 七类 page family + frontmatter 字段重复 ~7 处 | 见 C2/B2；workflow:72-80, structure:298-304, PRW×3 |
| B1 | FORM | P2 | PRW 5 个 workflow 重复 preflight/QMD/graph-rewrite/post-task/EPI-boundary | QMD 块×4、Graph-Aware Rewrite×3、record-request×5 |
| B2 | FORM | P3 | PRW `rules/` 与 `references/` 内容互相重复、边界模糊 | page-families.md == page-family-contract.md == wiki-writing-standard:36-48 |
| B3 | FORM | P3 | `always_read` 指向 5-14 行的薄 stub，且与 EPI canonical 重复 | PRW routing:10-11；epi-artifact-contract.md(14) |
| C1 | BNDRY | P1 | `epi-paper-deposition` 兼容 skill 自相矛盾且大量重复（173 行） | SKILL:15,17,23；formal-wiki-write:3,26-28 |
| C2 | BNDRY | P1 | 两插件对"谁写 wiki"自我模型不一致（EPI 视 PRW 为 level-5 adapter；PRW 自视 canonical 已内化） | epi-linkage:27-41,173；structure:167,302,439 vs PRW SKILL:65 |
| C3 | BNDRY | P2 | 只读 wiki 问答双实现（EPI `wiki-ask` + PRW `ask_wiki`） | wiki_query.py(805)；workflow.md:66；PRW ask-wiki.md |
| C4 | BNDRY | P3 | 双 handoff artifact 并存且都 required（`wiki_deposition_task.json` + `wiki-ingest-brief.json`） | epi-artifact-contract:5-6；extract:14 |
| D1 | FORM | P2 | `orchestrator.py` 2215 行/51 函数，`run_dry_run` 单函数 ~310 行，混 6 类职责 | orchestrator.py:892-1203 等 |
| D2 | FORM | P2 | 多个单体模块（1000-1634 行）；插件自身已标记不该再膨胀 | stage_wiki 1451 / run_index 1260 / wiki_ingest_record 1057 / paper_search_adapter 1634；AGENTS.md:14 |
| D3 | FORM | P3 | `_write_json` 是 `write_json_atomic` 的冗余私有别名（用 30×）——非 bug，纯冗余 | orchestrator.py:91 |
| E1 | FORM | P3 | EPI `plugin.json` `description` 过时过窄，与自身 long/short 描述矛盾 | epi plugin.json:4 |
| F1 | EFFECT | P2 | EPI→PRW 仍手动 hand-across（PRW→EPI 已半自动） | workflow.md:62,64 |
| F2 | EFFECT | P2 | critic→redo 无"自动重做直到 pass/上限"单命令 | epi-linkage:215,224 |

---

## A. 文档重复与 canonical 源歧义（EPI docs）—— 最大维护税

### A1 [P1·FORM] pipeline 在 4 个中文文档里各讲一遍
EPI 的同一条 8 阶段链路被完整叙述了至少四次：
- `epi-linkage.md`（§主链路 1–9，行 43–235，含每个 artifact、CLI、gate）
- `overview.zh.md`（§工作流总链路 0–8，行 41–319，再次列出每阶段 artifact 路径与命令）
- `structure.md`（CLI 分组 + 模块职责 + vault artifact 树）
- `workflow.md`（行 47、70 两段巨型 runbook）

用户**已声明** canonical 规则：`epi-linkage.md:272`"完整链路事实以本文档为准；workflow/evaluation/config 保持入口索引/最小话术"。问题是**执行漂移**：`overview.zh.md`(445 行) 名义是"中文导航层"(overview:10)，实际是第二份完整 pipeline 叙述，与 epi-linkage 近乎逐段重叠。每次链路语义变化要同步 ≥2 份全量文档 → 漂移源。

**修复**：让 `overview.zh.md` 真正瘦成导航——保留"三层心智模型表"(overview:29-39，有价值)、阅读顺序、artifact 速查；删除逐阶段 artifact 重述，改为指向 `epi-linkage.md` 的锚点。pipeline 事实**唯一** canonical = `epi-linkage.md`。**工作量**：中（主要是删+加指针，不改行为）。

### A2 [P1·FORM] `workflow.md` 违反自身"短入口"定位
`workflow.md` 被 `epi-linkage:15` / `overview:9` / `structure` 一致声明为"安装后日常使用的**短**流程入口"。但 `workflow.md:47` 是一段 ~1000 字、`workflow.md:70` 是一段 ~700 字的 runbook 巨段，把 acquire/identity-check/parse/staging/handoff/record 的全部细节塞进散文。这正是用户请求里"编写形式有问题"的典型样本。

**修复**：把 47/70 两段拆成（命令清单 + 一句话职责 + 指向 epi-linkage 对应 §的链接）。`workflow.md` 回到 ≤2 屏的短入口。**工作量**：低-中。

### A3 [P2·FORM] canonical 层级在 4 处各自声明
`epi-linkage:5-15`、`overview:5-10`、`structure:3`、`progress:3` 各写了一份"谁是权威、谁是配套"的清单，措辞不一致（例如 overview 把自己定位"中文导航"，structure 把 epi-linkage 定位"端到端行为契约"，progress 说自己"不替代"另两份）。读者要拼四处才能确认 single source of truth。

**修复**：把"doc map / 权威分工"收敛到**一处**（建议 `epi-linkage.md` 顶部或 README 的一个 section），其余文档顶部只留一行指针。**工作量**：低。

### A4 [P3·FORM] `progress.md` 是 changelog + file-list
`progress.md`(447 行) 把"当前状态/风险/下一步"与一长串"本轮/上一轮变更范围 + 受影响文件清单"(行 64–277) 混在一起。文件清单是 `git log`/`git diff` 的职责，放进受测文档会持续膨胀（用户自己在 `progress.md:443` / `epi-linkage:270` 也担心 deferred-token）。

**修复**：`progress.md` 只留"当前定位 + 最近一轮健康检查 + 已知风险 + 下一步"快照；历史轮次与 file-list 移到 `CHANGELOG.md` 或直接依赖 git。**工作量**：低。

---

## B. PRW 内部重复

### B1 [P2·FORM] 5 个 workflow 重复同一批 boilerplate
PRW 的 `extract-papers / check-wiki / redo-extraction / update-wiki / ask-wiki` 反复内联同样的段落：
- **QMD Compatibility** 块 × 4：`extract:53-55`、`check:68-70`、`redo:118-120`、`update:64-66`（措辞高度雷同）。
- **Graph-Aware Rewrite** 块 × 3：`redo:53-63`、`update:19-36`、`wiki-writing-standard:21-34`。
- **"先读 wiki-writing-standard + paper-wiki-language"** × 4（每个写入 workflow 开头）。
- **prw-record-request.json schema** × 5：`extract:49`、`redo:62`、`update:35`、`wiki-writing-standard:33`、`epi-integration:19`。
- **post-task check** × 5（都指向 check-wiki，但又各自复述一遍要检查项）。

`ask-wiki.md`(34 行只读) 是反例，干净。

**修复**：抽出共享 reference（如 `references/qmd-policy.md`、`references/graph-aware-rewrite.md`、`references/epi-record-handoff.md`、`references/post-task-check.md`），每个 workflow 改为一行"按 `references/xxx.md` 执行"。**工作量**：中（PRW 侧，低风险）。

### B2 [P3·FORM] `rules/` 与 `references/` 内容重叠
- `rules/page-families.md`(20) ≈ `references/page-family-contract.md`(5) ≈ `wiki-writing-standard.md:36-48` ≈ 全部 EPI 文档的"七类目录"。
- `rules/formal-page-frontmatter.md`(9) ≈ `wiki-writing-standard.md:98-118`。
- `rules/source-trust.md`(5) ≈ `SKILL.md:60` 的"untrusted data"行。

`rules/` 与 `references/` 的职责边界没定义清楚，同一事实在两处都有薄拷贝。

**修复**：定义 `rules/` = 单一 canonical 约束来源；`references/` 只放"如何做"的细节（如 references-page-anatomy）。删除 `page-family-contract.md` 等纯重复 stub，或改成一行指针。**工作量**：低。

### B3 [P3·FORM] `always_read` 指向薄 stub 且与 EPI 重复
PRW `routing.yaml:10-11` + `SKILL.md:37` 要求每个任务 always-read `epi-artifact-contract.md`(14 行) 和 `page-family-contract.md`(5 行)。前者与 EPI canonical（`epi-linkage` §3/§7、`structure` vault 树）描述同一份 artifact 契约——跨插件第二处定义，漂移风险。

**修复**：`epi-artifact-contract.md` 改为"指向 EPI canonical + 仅列 PRW 实际消费的字段"；`page-family-contract` 并入 B2 的 canonical。**工作量**：低。

---

## C. 跨插件边界漂移与重叠（Q3：允许重新划边界）

### C1 [P1·BNDRY] `epi-paper-deposition` 兼容 skill 自相矛盾
`epi-paper-deposition/SKILL.md`(62) + `workflows/formal-wiki-write.md`(111) = 173 行，但其主旨反复是"改用 `$paper-research-wiki`"（`SKILL:15,17,23`；`formal-wiki-write:3,26-28`）。`formal-wiki-write.md:26-28` 甚至写"invoke `$paper-research-wiki` instead of continuing in this compatibility adapter"——**runbook 自我否定**。与此同时它又：
- 第 6/7 次重述 page family / frontmatter / QMD boundary（`SKILL:52-62`、`formal-wiki-write:43-111`）；
- 给出完整 external 栈 runbook（`llm-wiki`、`wiki-ingest`、`wiki-lint`、`tag-taxonomy`、`wiki-synthesize`、`wiki-dedup`、`cross-linker`）——见 C2。

**修复（建议重划）**：压成 ≤15 行的薄 alias——"遇到 legacy `wiki_deposition_task.json` / `epi-wiki-deposition` 提及 → 一律路由到 PRW `$paper-research-wiki`；不再在此写正文"。删除 external-stack runbook 与所有重复 contract。**工作量**：低（删除为主），但属边界决定，需用户拍板。

### C2 [P1·BNDRY] 两插件对"谁写 wiki"的自我模型不一致
- **EPI 视角**：`epi-linkage.md:27-41` 的 8 级 `wiki_rule_source_model` 把 PRW 放在 **level 5**，把外部 `llm-wiki`/`wiki-ingest`/`obsidian-markdown` 放 level 9 作"执行 adapter"；"required skill stack"在 `workflow.md:70`、`structure.md:167,302,439`、`epi-linkage:173` 反复列出 `llm-wiki, wiki-ingest, wiki-context-pack, wiki-lint, wiki-stage-commit, wiki-status, wiki-query, tag-taxonomy`。
- **PRW 视角**：`SKILL.md:65`"PRW has internalized the Ar9av/obsidian-wiki skill patterns into local PRW workflows; **do not fetch upstream** repositories during normal PRW runs"。

即：EPI 仍把最终写入建模为"PRW + 一堆外部 obsidian-wiki skills 协作"，而 PRW 宣称自己已内化、是 canonical 整体写入层。跟随 EPI handoff 的 agent 会被指示去用一批 PRW 认为已被取代的外部 skill。这是本审计里**概念层面最深的漂移**。

> 背景说明：8 级模型源于"下游曾是外部 `obsidian-wiki-dev/wiki-skills`"的时代（见 memory `epi-two-system-architecture`）。PRW 进 repo 并成为 canonical 后，该模型部分变成 legacy。

**修复（建议重划）**：统一为"PRW `$paper-research-wiki` = canonical 写入/维护层（已内化 Ar9av/obsidian patterns）；external obsidian-wiki repos = 可选 upstream 参考，正常运行不依赖"。据此：(a) EPI handoff 的"required skill stack"改成只点 `$paper-research-wiki`（+ provenance 边界），external 列表降级为"可选参考"；(b) `wiki_rule_source_model` 简化层级（PRW 升为主执行层，level 6-9 外部仓库降为 optional reference）。**工作量**：中（跨多文档 + 可能动 `wiki_handoff_contracts.py` / `wiki_contracts.py` 的字段断言与对应测试）。**需用户拍板**。

### C3 [P2·BNDRY] 只读 wiki 问答双实现
EPI 侧 `wiki_query.py`(805) 提供 CLI `wiki-ask`；PRW 侧 `ask_wiki` route + `ask-wiki.md`。两者都做"只读正式图谱检索 + `【Wiki 证据】/【综合判断】/【推断】/【边界】` 标注 + correction candidates"。`workflow.md:66` 甚至把 EPI 的 CLI 称作"read-only **PRW** formal graph query CLI"——命名都暗示它本属 PRW。用户/agent 不清楚两者何时用哪个。

**修复（择一，需用户定）**：
- (a) **归 PRW**：问答归 PRW `ask_wiki`（wiki 层自然归属）；EPI CLI 保留为"无 PRW 时 fallback / 程序化入口"，并在文档明确这是同一能力的两个入口、对话场景优先 PRW。
- (b) **明确分工**：EPI `wiki-ask` = 程序化/CI 入口（CLI、`--json`），PRW `ask_wiki` = 对话入口；文档显式写清，避免"看起来重复"。
**工作量**：低-中（主要是文档归属 + 可能加一句互相指引；不一定删代码）。

### C4 [P3·BNDRY] 双 handoff artifact 并存
`epi-artifact-contract.md:5-6`、`extract:14`、`paper-gate` 同时 required `wiki_deposition_task.json`（legacy）与 `wiki-ingest-brief.json`。两份 handoff 长期并轨增加 EPI 生成端与 PRW 消费端的双重维护。

**修复**：确认 `wiki-ingest-brief.json` 为 canonical；`wiki_deposition_task.json` 标 deprecated（保留读取兼容、停止当作必需），给一个迁移期。**工作量**：中（动 `stage_wiki.py` 生成 + gate 检查 + PRW 消费 + 测试）。

---

## D. Python 单体与代码形

### D1 [P2·FORM] `orchestrator.py` 2215 行混 6 类职责
51 个顶层函数（`grep` 实测）。`run_dry_run` 单函数 892–1203 ≈ **310 行**。模块内混杂：JSON helper（`_write_json`）、source-coverage 格式化（`_source_coverage_from_*`，~414-516）、query-plan 构建（`_build_dry_run_query_plan`/`_ranking_keywords_from_profile`/`_venue_tiers_from_profile`/`_filter_domains_from_profile`，205-307）、repair-report 写入（`_repair_report_contract`/`_write_repair_*`，656-892）、以及真正的多阶段编排（`run_dry_run`/`advance_paper_batch`/`prepare_ranked_papers_from_run`）。

**修复（建议拆分）**：`dry_run_pipeline.py`（run_dry_run + query-plan helpers）｜`batch_advance.py`（advance_paper*/select）｜`prepare_ranked.py`｜`source_coverage.py`｜`repair_reports.py`。`orchestrator.py` 只留薄编排 + `main()`。**工作量**：高，**必须 TDD**（见 D-约束）。建议单独成 spec。

### D2 [P2·FORM] 多个单体模块，且插件自身已标记
`stage_wiki.py`(1451)、`paper_search_adapter.py`(1634)、`run_index.py`(1260)、`wiki_ingest_record.py`(1057)、`cli.py`(870)、`paper_gate.py`(837)、`wiki_query.py`(805)。`AGENTS.md:14` 明确"Prefer focused workflow modules over growing `cli.py`, `orchestrator.py`, or `stage_wiki.py`"——**问题已知、指引已写，但重构未做**。`docs/superpowers/plans/2026-06-04-epi-stability-refactor.md` 也存在，说明曾计划过。

**修复**：按职责把每个 >1000 行模块拆 2-3 个聚焦模块；优先 `stage_wiki.py`（handoff brief/promotion-plan/reading-report/source-review-contract 是清晰的拆分线）。**工作量**：高，**必须 TDD**。

### D3 [P3·FORM] `_write_json` 冗余别名（非 bug）
`orchestrator.py:91` `_write_json` 仅 `return write_json_atomic(...)`，被调用 30×。**已核实不是原子性绕过**，只是冗余私有别名。**修复**：直接调 `write_json_atomic`，删别名。顺手清理，零风险。

### D-约束（非问题，执行须知）
宿主 `tests/epi` 有 300+ 测试（`progress.md` 记 303 passing），加 `plugins/epi/tests` 的 skill-bundle contract + `tests/paper_research_wiki` 的 PRW contract。任何 D 类重构必须：TDD、保持全绿、bump 两个 `plugin.json` 版本、同步受测文档（`test_current_docs.py` / `test_epi_linkage_doc.py` 会校验 docs）。

---

## E. Manifest / 元数据卫生（快速赢）

### E1 [P3·FORM] EPI `plugin.json` `description` 过时
`plugins/epi/.codex-plugin/plugin.json:4` `"description": "Search and rank academic papers for an EPI wiki."` 只覆盖检索排序，与同文件 `shortDescription`(行 22，全链路) / `longDescription`(行 23) 及 README 矛盾。marketplace 列表可能展示这条短的。

**修复**：一行改写成与 longDescription 一致的全链路定位。**工作量**：极低。PRW 的 `description`(行 4) 较准确，可对照。

---

## F. 工作流效果 / 自动化缺口（本轮次要，列全备选）

### F1 [P2·EFFECT] EPI→PRW 仍手动 hand-across
EPI 写 `wiki-agent-trigger.json` 后，需用户再 `@prw`/`@EPI`（`workflow.md:62`）。反向 PRW→EPI 的 record 已通过 `prw-record-request.json` + `record-wiki-ingest --from-prw-request` 半自动化（`workflow.md:64`，最近两个 commit）。即闭环的一半已自动、另一半仍手动。

**说明**：跨 Codex 插件的自动触发受平台限制（memory `epi-workflow-vision-and-gaps` gap #2，部分 by design）。**可做**：补一份"EPI↔PRW 衔接 SOP"单页，或在 EPI trigger 输出里直接给出 PRW 调用话术，降低手动摩擦。**工作量**：低（文档）/中（约定）。

### F2 [P2·EFFECT] critic→redo 无单命令自动循环
`redo-read --from-revision-plan --recritic` + `needs_reader_repair` 队列已存在（`epi-linkage:215,224`），但"自动重做直到 pass 或上限"未封装成单命令，需外层 agent/workflow loop（memory gap #1）。**可做**：加一个 `redo-until-pass --max-iters N` 包装命令。**工作量**：中（新 CLI + 测试）。

---

## 建议执行顺序

1. **快速赢（半天内，低风险，建立动量）**：E1（plugin.json 描述）→ D3（删 `_write_json` 别名）→ B2/B3（PRW rules/references 去重）→ A4（progress.md 瘦身）。
2. **最高维护税（编写形式核心）**：A2（workflow.md 巨段拆分）→ A1（overview.zh 瘦成导航）→ A3（canonical doc map 收敛到一处）。
3. **边界澄清（需你拍板）**：C2（统一"谁写 wiki"自我模型）+ A5（page-family/frontmatter 单一 canonical）→ C1（折叠 epi-paper-deposition 为薄 alias）→ C3（只读 ask 归属）→ C4（双 artifact 收敛）。
4. **PRW 编写形式**：B1（5 个 workflow 抽共享 reference）。
5. **代码重构（单独成 spec，TDD）**：D2（先拆 `stage_wiki.py`）→ D1（拆 `orchestrator.py`）。
6. **效果/自动化（独立轨，你已次要化）**：F1 → F2。

## 下一步

请从上表挑选要推进的条目（可按"建议执行顺序"的批次选，或单点选）。每个被选条目我会单独走 `brainstorm → 写 spec（docs/superpowers/specs/）→ 实现（TDD + 版本 bump + 文档同步）`。本审计未做任何代码/文档改动。
