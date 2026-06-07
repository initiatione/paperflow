# S3a — EPI/PRW 文档与契约 canonical 化（A1–A5 · C3 · C4 · E1 · D3）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 EPI/PRW 文档层的重复与 canonical 源歧义，并修两处机械问题——不改任何运行链路语义（C2/C1 契约变更已划入独立的 S3b）。

**Architecture:** 纯文档 + 元数据 + 一处行为保持重构（D3）。`epi-linkage.md` 保持为 pipeline 事实唯一 canonical；`overview.zh.md`/`workflow.md`/`progress.md` 瘦成导航/短入口/快照；page-family/frontmatter 人读 canonical 指向 PRW `rules/wiki-writing-standard.md`。每项用一条**文档断言测试**锁定不变量（TDD：先写失败断言，再改文档转绿）。

**Tech Stack:** Python 3.13 + pytest（`tests/epi/test_current_docs.py`、`tests/epi/test_epi_linkage_doc.py`、`tests/paper_research_wiki/test_plugin_contract.py`）；Markdown 文档；Codex `plugin.json`。

**Spec:** `docs/superpowers/specs/2026-06-07-epi-prw-contract-doc-canonicalization-design.md` ｜ **Audit:** `docs/audits/2026-06-07-epi-prw-optimization-audit.md`

**不在 S3a（明确排除）：** C2（`REQUIRED_WIKI_SKILLS` 迁移 + brief/gate 传播）、C1（`epi-paper-deposition` 薄化）——这两项是跨切面契约变更，落在 **S3b** 单独 plan；B1/B2/B3（PRW 结构去重）落在 **S2**。

---

## File Structure

**修改的文档（内容编辑，保留各测试已断言的字符串）：**
- `plugins/epi/docs/overview.zh.md` — 瘦成导航层（A1）
- `plugins/epi/docs/workflow.md` — 拆巨段为短入口（A2）
- `plugins/epi/docs/epi-linkage.md` — 唯一 doc map + 各 canonical 指针（A3/A5/C3/C4）；保持 pipeline 事实
- `plugins/epi/docs/structure.md` — 层级声明改为指针（A3）
- `plugins/epi/docs/progress.md` — 瘦成快照 + 指向 CHANGELOG（A4）
- `plugins/PRW/rules/wiki-writing-standard.md` — 顶部声明 canonical（A5）
- `plugins/PRW/skills/paper-research-wiki/workflows/ask-wiki.md`、`plugins/PRW/docs/epi-integration.md`、`plugins/PRW/skills/paper-research-wiki/references/epi-artifact-contract.md`、`plugins/PRW/skills/paper-research-wiki/workflows/extract-papers.md` — C3/C4 标注

**新建：**
- `plugins/epi/docs/CHANGELOG.md` — 迁出的逐轮历史（A4）

**元数据/代码：**
- `plugins/epi/.codex-plugin/plugin.json` — description（E1）+ version 0.2.1（Task 10）
- `plugins/PRW/.codex-plugin/plugin.json` — version 0.2.1（Task 10）
- `plugins/epi/scripts/build/epi/orchestrator.py` — 删 `_write_json` 别名（D3）

**测试（新增断言）：**
- `tests/epi/test_current_docs.py` — EPI 侧不变量（Task 1,3,4,5,6,7,8,9,10）
- `tests/paper_research_wiki/test_plugin_contract.py` — PRW 侧不变量（Task 8,9 PRW 文件）

**执行顺序**：Phase 1 快速赢（T1 E1 → T2 D3 → T3 C4）→ Phase 2 文档 canonical（T4 A3 → T5 A1 → T6 A2 → T7 A4 → T8 A5 → T9 C3）→ Phase 3 收尾（T10 版本 → T11 全量验证）。

---

## Phase 1 — 快速赢

### Task 1: E1 — EPI `plugin.json` description 全链路化

**Files:**
- Test: `tests/epi/test_current_docs.py`
- Modify: `plugins/epi/.codex-plugin/plugin.json:4`

- [ ] **Step 1: 写失败测试**（追加到 `tests/epi/test_current_docs.py` 末尾）

```python
def test_epi_plugin_description_reflects_full_pipeline():
    manifest = json.loads(
        (PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    desc = manifest["description"]
    assert desc != "Search and rank academic papers for an EPI wiki."
    assert any(k in desc for k in ["parse", "MinerU", "critic", "handoff", "wiki ingest"])
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/epi/test_current_docs.py::test_epi_plugin_description_reflects_full_pipeline -v`
Expected: FAIL（`assert desc != "Search and rank..."`）

- [ ] **Step 3: 改 `plugin.json:4` `description`**

```json
  "description": "Profile-driven academic paper discovery, OA acquisition, MinerU parsing, reader/critic review, and agent-mediated wiki handoff feeding the PRW paper wiki.",
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/epi/test_current_docs.py::test_epi_plugin_description_reflects_full_pipeline -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/epi/test_current_docs.py plugins/epi/.codex-plugin/plugin.json
git commit -m "fix(epi): full-pipeline plugin.json description (E1)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task 2: D3 — 删 `orchestrator.py` 的 `_write_json` 冗余别名（行为保持重构）

**Files:**
- Modify: `plugins/epi/scripts/build/epi/orchestrator.py`（删 def 91-92；调用点 `_write_json(` → `write_json_atomic(`）

- [ ] **Step 1: 确认基线绿**

Run: `python -m pytest tests/epi -q`
Expected: PASS（记录通过数，作为重构前后对照）

- [ ] **Step 2: 删别名定义**

删除 `orchestrator.py:91-92`：
```python
def _write_json(path: Path, payload: object) -> None:
    write_json_atomic(path, payload)
```
（`write_json_atomic` 已在文件顶部从 `epi.artifacts` 导入；删 def 后不需新增 import。）

- [ ] **Step 3: 替换所有调用点**

在 `orchestrator.py` 内把剩余 `_write_json(` 全部替换为 `write_json_atomic(`（Edit `replace_all: true`，old=`_write_json(`，new=`write_json_atomic(`）。删 def 后该串只剩调用点，无残留定义。

- [ ] **Step 4: 确认无残留 + 全绿（行为保持）**

Run: `grep -n "_write_json" plugins/epi/scripts/build/epi/orchestrator.py` → 预期无输出
Run: `python -m pytest tests/epi -q`
Expected: PASS，通过数与 Step 1 相同（纯重构，零行为变化）

- [ ] **Step 5: Commit**

```bash
git add plugins/epi/scripts/build/epi/orchestrator.py
git commit -m "refactor(epi): drop redundant _write_json alias for write_json_atomic (D3)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task 3: C4 — `wiki_deposition_task.json` 文档标 deprecated（canonical=brief）

**Files:**
- Test: `tests/epi/test_current_docs.py`、`tests/paper_research_wiki/test_plugin_contract.py`
- Modify: `plugins/epi/docs/epi-linkage.md`、`plugins/PRW/skills/paper-research-wiki/references/epi-artifact-contract.md`、`plugins/PRW/docs/epi-integration.md`

- [ ] **Step 1: 写失败测试**

追加到 `tests/epi/test_current_docs.py`：
```python
def test_handoff_artifact_contract_marks_brief_canonical_and_task_deprecated():
    linkage = _read("epi-linkage.md")
    assert "wiki-ingest-brief.json" in linkage
    assert "wiki_deposition_task.json" in linkage
    assert "deprecated" in linkage.lower() or "已废弃" in linkage
```
追加到 `tests/paper_research_wiki/test_plugin_contract.py`：
```python
def test_prw_artifact_contract_marks_task_deprecated():
    contract = (PUBLIC_SKILL / "references" / "epi-artifact-contract.md").read_text(encoding="utf-8")
    assert "wiki-ingest-brief.json" in contract
    assert "deprecated" in contract.lower() or "已废弃" in contract
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/epi/test_current_docs.py::test_handoff_artifact_contract_marks_brief_canonical_and_task_deprecated tests/paper_research_wiki/test_plugin_contract.py::test_prw_artifact_contract_marks_task_deprecated -v`
Expected: FAIL（缺 deprecated 标注）

- [ ] **Step 3: 加 deprecation 标注**

在 `epi-linkage.md` §8（Wiki Ingest Handoff）插入一行：
> 注：`wiki-ingest-brief.json` 是 canonical handoff；`wiki_deposition_task.json` 已 deprecated（仍读兼容，迁移意图见 audit C4），新链路不应再依赖它作为必需 artifact。

在 PRW `references/epi-artifact-contract.md` 顶部"Required inputs"前插入：
> canonical handoff = `wiki-ingest-brief.json`；`wiki_deposition_task.json` 为 deprecated 兼容 artifact（仍读，不应新增依赖）。

在 PRW `docs/epi-integration.md` 的"Required inputs"句后补同样一句。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/epi/test_current_docs.py::test_handoff_artifact_contract_marks_brief_canonical_and_task_deprecated tests/paper_research_wiki/test_plugin_contract.py::test_prw_artifact_contract_marks_task_deprecated -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/epi/test_current_docs.py tests/paper_research_wiki/test_plugin_contract.py plugins/epi/docs/epi-linkage.md plugins/PRW/skills/paper-research-wiki/references/epi-artifact-contract.md plugins/PRW/docs/epi-integration.md
git commit -m "docs(epi/prw): mark wiki_deposition_task.json deprecated, brief canonical (C4)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Phase 2 — 文档 canonical 化

### Task 4: A3 — 单一 doc map（epi-linkage 为权威分工唯一处）

**Files:**
- Test: `tests/epi/test_current_docs.py`
- Modify: `plugins/epi/docs/epi-linkage.md`（顶部"配套文档"升级为权威 doc map）、`overview.zh.md`/`structure.md`/`progress.md`（层级声明改为一行指针）

- [ ] **Step 1: 写失败测试**

```python
def test_single_doc_map_in_linkage_others_point_to_it():
    linkage = _read("epi-linkage.md")
    # canonical doc map 已含全部配套文档指针（沿用 test_linkage_doc_points_to_... 的要求）
    for ref in ["docs/structure.md", "docs/progress.md", "docs/config.md", "docs/overview.zh.md", "docs/workflow.md"]:
        assert ref in linkage
    # 其余文档不再各自声明权威层级，只留一行指向 epi-linkage
    for name in ["overview.zh.md", "structure.md", "progress.md"]:
        assert "docs/epi-linkage.md" in _read(name)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/epi/test_current_docs.py::test_single_doc_map_in_linkage_others_point_to_it -v`
Expected: FAIL（epi-linkage 配套清单缺 overview/workflow 条目，或其它文档未统一指针）

- [ ] **Step 3: 改文档**

在 `epi-linkage.md` "配套文档" 段落补全为权威 doc map（含 `docs/overview.zh.md`、`docs/workflow.md`、`docs/structure.md`、`docs/progress.md`、`docs/config.md` 各一行职责）。
在 `overview.zh.md`、`structure.md`、`progress.md` 顶部把各自的"权威分工/配套文档"声明替换为单行：
> 文档权威分工（doc map）见 `docs/epi-linkage.md` 顶部；本文件只承担 <导航 / 结构 / 进度快照>。

- [ ] **Step 4: 跑测试确认通过 + 不回归**

Run: `python -m pytest tests/epi/test_current_docs.py -v`
Expected: PASS（新测试 + 既有 `test_linkage_doc_points_to_structure_progress_and_config_docs` 仍绿）

- [ ] **Step 5: Commit**

```bash
git add tests/epi/test_current_docs.py plugins/epi/docs/epi-linkage.md plugins/epi/docs/overview.zh.md plugins/epi/docs/structure.md plugins/epi/docs/progress.md
git commit -m "docs(epi): single canonical doc map in epi-linkage, others point to it (A3)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task 5: A1 — `overview.zh.md` 瘦成导航层

**Files:**
- Test: `tests/epi/test_current_docs.py`
- Modify: `plugins/epi/docs/overview.zh.md`

- [ ] **Step 1: 写失败测试**

```python
def test_overview_zh_is_navigation_not_second_pipeline():
    text = _read("overview.zh.md")
    assert text.count("\n") < 200  # 导航层；当前 445 行是第二份完整 pipeline 叙述
    assert "docs/epi-linkage.md" in text          # 把 pipeline 事实委派给 canonical
    assert ("三层" in text) or ("心智模型" in text)  # 保留心智模型地图
    assert ("推荐阅读顺序" in text) or ("阅读顺序" in text)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/epi/test_current_docs.py::test_overview_zh_is_navigation_not_second_pipeline -v`
Expected: FAIL（行数 ≥ 200）

- [ ] **Step 3: 重构 `overview.zh.md`**

保留：一句话定位、`## 核心心智模型`（三层表）、`## 推荐阅读顺序`、`## 常用命令速查`，并在"工作流总链路"处改为：
> 完整 8 阶段链路事实（artifact 路径、CLI 语义、安全门）见 `docs/epi-linkage.md` §主链路；本文件只给导航地图。

删除：`### 0–8` 各阶段的逐条 artifact 路径与命令重述（当前约行 41–319 的展开），用上面一句 + 指向 epi-linkage 锚点替代。结果应 < 200 行。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/epi/test_current_docs.py -v`
Expected: PASS（overview.zh 不在其它断言读取列表，无回归风险）

- [ ] **Step 5: Commit**

```bash
git add tests/epi/test_current_docs.py plugins/epi/docs/overview.zh.md
git commit -m "docs(epi): slim overview.zh.md to a navigation layer (A1)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task 6: A2 — `workflow.md` 拆巨段为短入口

**Files:**
- Test: `tests/epi/test_current_docs.py`
- Modify: `plugins/epi/docs/workflow.md`

- [ ] **Step 1: 写失败测试**

```python
def test_workflow_md_is_short_entry_without_runbook_paragraphs():
    text = _read("workflow.md")
    longest_line = max((len(line) for line in text.splitlines()), default=0)
    assert longest_line < 1200          # 行 47/70 的巨段约 3000–6000 字
    assert "epi-linkage" in text         # 细节委派给 canonical
    # 保留 easyscholar 契约（test_docs_document_easyscholar_enrichment_contract 也要求）
    assert "EasyScholar" in text or "easyscholar" in text
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/epi/test_current_docs.py::test_workflow_md_is_short_entry_without_runbook_paragraphs -v`
Expected: FAIL（最长行 ≫ 1200）

- [ ] **Step 3: 拆 `workflow.md` 行 47 与行 70 的巨段**

把两段散文 runbook 改写为：每条命令一行 + 一句话职责 + "完整语义见 `docs/epi-linkage.md` §N"。保留已有的 powershell 命令块。**务必保留** easyscholar 契约相关语句（`test_docs_document_easyscholar_enrichment_contract` 断言 workflow.md 含 EasyScholar enrichment 内容）与 `report`/`prepare-ranked`/`wiki-ask` 命令名。

- [ ] **Step 4: 跑测试确认通过 + 关键回归**

Run: `python -m pytest tests/epi/test_current_docs.py::test_workflow_md_is_short_entry_without_runbook_paragraphs tests/epi/test_current_docs.py::test_docs_document_easyscholar_enrichment_contract -v`
Expected: PASS（两者皆绿）
Run: `python -m pytest tests/epi/test_current_docs.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/epi/test_current_docs.py plugins/epi/docs/workflow.md
git commit -m "docs(epi): split workflow.md runbook paragraphs into short entry (A2)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task 7: A4 — `progress.md` 瘦成快照 + 历史迁入 `CHANGELOG.md`

**Files:**
- Test: `tests/epi/test_current_docs.py`
- Create: `plugins/epi/docs/CHANGELOG.md`
- Modify: `plugins/epi/docs/progress.md`

- [ ] **Step 1: 写失败测试**

```python
def test_progress_md_snapshot_history_in_changelog():
    progress = _read("progress.md")
    changelog = (DOCS / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "本轮相关变更范围" not in progress      # 逐轮 file-list 已迁出
    assert "下一步" in progress and "已知风险" in progress  # 快照段保留
    assert "CHANGELOG.md" in progress              # 指向历史
    assert len(changelog.splitlines()) > 20         # 历史落到 CHANGELOG
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/epi/test_current_docs.py::test_progress_md_snapshot_history_in_changelog -v`
Expected: FAIL（无 CHANGELOG.md / progress 仍含 file-list）

- [ ] **Step 3: 迁移历史 + 瘦身**

新建 `plugins/epi/docs/CHANGELOG.md`，把 `progress.md` 中"本轮相关变更范围"及逐轮受影响 file-list（约行 64–277）整段迁入，按时间倒序保留。
`progress.md` 留：`当前定位`、`最近一轮健康检查`、`最近验证`（保 `test_progress_doc_records_status_verification_and_next_steps` 要求的 status/verification/next-steps）、`已知风险`、`下一步`，并加一行：`逐轮变更历史见 docs/CHANGELOG.md`。

- [ ] **Step 4: 跑测试确认通过 + 不回归**

Run: `python -m pytest tests/epi/test_current_docs.py::test_progress_md_snapshot_history_in_changelog tests/epi/test_current_docs.py::test_progress_doc_records_status_verification_and_next_steps -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/epi/test_current_docs.py plugins/epi/docs/progress.md plugins/epi/docs/CHANGELOG.md
git commit -m "docs(epi): slim progress.md to snapshot, move history to CHANGELOG (A4)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task 8: A5 — page-family/frontmatter 人读 canonical = PRW `wiki-writing-standard.md`

**Files:**
- Test: `tests/epi/test_current_docs.py`、`tests/paper_research_wiki/test_plugin_contract.py`
- Modify: `plugins/PRW/rules/wiki-writing-standard.md`（顶部声明 canonical）、`plugins/epi/docs/epi-linkage.md`/`structure.md`/`workflow.md`（指针）、`plugins/epi/scripts/build/epi/wiki_contracts.py`（注释指明人读 canonical）

- [ ] **Step 1: 写失败测试**

`tests/paper_research_wiki/test_plugin_contract.py`：
```python
def test_wiki_writing_standard_declares_itself_canonical():
    rule = (PLUGIN / "rules" / "wiki-writing-standard.md").read_text(encoding="utf-8")
    assert "canonical" in rule.lower() or "唯一权威" in rule
    assert "page" in rule.lower() and "frontmatter" in rule.lower()
```
`tests/epi/test_current_docs.py`：
```python
def test_epi_docs_point_to_prw_canonical_for_page_family_frontmatter():
    assert "rules/wiki-writing-standard.md" in _read("epi-linkage.md")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/epi/test_current_docs.py::test_epi_docs_point_to_prw_canonical_for_page_family_frontmatter tests/paper_research_wiki/test_plugin_contract.py::test_wiki_writing_standard_declares_itself_canonical -v`
Expected: FAIL

- [ ] **Step 3: 标 canonical + 加指针**

`wiki-writing-standard.md` 顶部（标题下）加一句：
> 本文件是 PRW 正式页 page-family 与 frontmatter 的 **canonical**（唯一权威）人读契约；EPI 文档与 PRW 其它 rule/reference 只应指向本文件，不复制字段清单。

`epi-linkage.md`/`structure.md`/`workflow.md` 中"七类目录 + frontmatter 字段"列表处，保留测试已断言的最小内容，并加一行：
> 完整 page-family/frontmatter 契约见 PRW `plugins/PRW/rules/wiki-writing-standard.md`（canonical）。

`wiki_contracts.py` 在 `FORMAL_PAGE_FAMILIES` / `FORMAL_FRONTMATTER_REQUIRED_FIELDS` 上方加注释：
```python
# Code-enforcement copy of the page-family / frontmatter contract.
# Human-canonical prose lives in plugins/PRW/rules/wiki-writing-standard.md (A5).
```

- [ ] **Step 4: 跑测试确认通过 + 不回归**

Run: `python -m pytest tests/epi/test_current_docs.py tests/paper_research_wiki/test_plugin_contract.py -q`
Expected: PASS（含既有 page-family/frontmatter 断言）

- [ ] **Step 5: Commit**

```bash
git add tests/epi/test_current_docs.py tests/paper_research_wiki/test_plugin_contract.py plugins/PRW/rules/wiki-writing-standard.md plugins/epi/docs/epi-linkage.md plugins/epi/docs/structure.md plugins/epi/docs/workflow.md plugins/epi/scripts/build/epi/wiki_contracts.py
git commit -m "docs(epi/prw): PRW wiki-writing-standard is canonical page-family/frontmatter source (A5)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task 9: C3 — 只读问答归属（PRW `ask_wiki` 主入口，EPI `wiki-ask` 同源 fallback）

**Files:**
- Test: `tests/epi/test_current_docs.py`、`tests/paper_research_wiki/test_plugin_contract.py`
- Modify: `plugins/epi/docs/epi-linkage.md`/`overview.zh.md`/`workflow.md`（wiki-ask 段）、`plugins/PRW/skills/paper-research-wiki/workflows/ask-wiki.md`、`plugins/PRW/docs/epi-integration.md`

- [ ] **Step 1: 写失败测试**

`tests/epi/test_current_docs.py`：
```python
def test_read_only_ask_ownership_documented_epi_side():
    linkage = _read("epi-linkage.md")
    assert "wiki-ask" in linkage
    assert ("fallback" in linkage.lower()) or ("程序化" in linkage) or ("对话优先 PRW" in linkage)
```
`tests/paper_research_wiki/test_plugin_contract.py`：
```python
def test_ask_wiki_notes_epi_cli_is_same_source_fallback():
    ask = (PUBLIC_SKILL / "workflows" / "ask-wiki.md").read_text(encoding="utf-8")
    assert "wiki-ask" in ask
    assert ("fallback" in ask.lower()) or ("程序化" in ask) or ("同源" in ask)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/epi/test_current_docs.py::test_read_only_ask_ownership_documented_epi_side tests/paper_research_wiki/test_plugin_contract.py::test_ask_wiki_notes_epi_cli_is_same_source_fallback -v`
Expected: FAIL

- [ ] **Step 3: 加归属说明**

`epi-linkage.md` §`wiki-ask`（约行 207）/ `overview.zh.md` / `workflow.md` 的 wiki-ask 段补一句：
> 只读问答的对话主入口是 PRW `$paper-research-wiki` 的 `ask_wiki`；EPI `wiki-ask` CLI 是同源能力的 fallback / 程序化（`--json`）入口。对话场景优先 PRW。
PRW `ask-wiki.md` / `epi-integration.md` 补对称一句：
> 本 `ask_wiki` 是对话主入口；EPI `wiki-ask` CLI 为同源 fallback/程序化入口（同一正式图谱检索）。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/epi/test_current_docs.py tests/paper_research_wiki/test_plugin_contract.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/epi/test_current_docs.py tests/paper_research_wiki/test_plugin_contract.py plugins/epi/docs/epi-linkage.md plugins/epi/docs/overview.zh.md plugins/epi/docs/workflow.md plugins/PRW/skills/paper-research-wiki/workflows/ask-wiki.md plugins/PRW/docs/epi-integration.md
git commit -m "docs(epi/prw): document read-only ask ownership — PRW primary, EPI CLI fallback (C3)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Phase 3 — 收尾

### Task 10: 版本同步 0.2.1 + marketplace 一致

**Files:**
- Test: `tests/epi/test_current_docs.py`
- Modify: `plugins/epi/.codex-plugin/plugin.json`、`plugins/PRW/.codex-plugin/plugin.json`、`marketplace.json` 与 `.agents/plugins/marketplace.json`（若含版本/短描述镜像）、`plugins/epi/docs/CHANGELOG.md`（记一条 0.2.1）

- [ ] **Step 1: 写失败测试**

```python
def test_plugin_versions_bumped_to_0_2_1():
    for rel in ["plugins/epi/.codex-plugin/plugin.json", "plugins/PRW/.codex-plugin/plugin.json"]:
        manifest = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        assert manifest["version"] == "0.2.1"
        assert "v0.2.1" in manifest["interface"]["shortDescription"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/epi/test_current_docs.py::test_plugin_versions_bumped_to_0_2_1 -v`
Expected: FAIL（当前 0.2.0）

- [ ] **Step 3: bump 版本**

两个 `plugin.json`：`version` → `0.2.1`，`interface.shortDescription` 的 `v0.2.0` → `v0.2.1`。检查 `marketplace.json` / `.agents/plugins/marketplace.json` 是否镜像版本/短描述并同步。在 `CHANGELOG.md` 顶部加：`## 0.2.1 (2026-06-07) — S3a 文档/契约 canonical 化（A1–A5,C3,C4,E1,D3）`。

- [ ] **Step 4: 跑测试确认通过 + marketplace 测试**

Run: `python -m pytest tests/epi/test_current_docs.py::test_plugin_versions_bumped_to_0_2_1 tests/test_marketplace_manifest.py -v`
Expected: PASS（若 `test_marketplace_manifest.py` 另有版本断言，一并对齐）

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore(epi/prw): bump to 0.2.1 for S3a doc/contract canonicalization

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task 11: 全量验证

- [ ] **Step 1: 跑全量测试套件**

Run: `python -m pytest tests/epi tests/paper_research_wiki plugins/epi/tests -q`
Expected: PASS（全绿；与基线相比净增本计划新增的断言数）

- [ ] **Step 2: 插件结构校验（若本机配置了 validator）**

Run: `python -m json.tool plugins/epi/.codex-plugin/plugin.json >/dev/null && python -m json.tool plugins/PRW/.codex-plugin/plugin.json >/dev/null && git diff --check`
Expected: JSON 合法、无 whitespace error

- [ ] **Step 3: 抽查不变量**

确认：`overview.zh.md` < 200 行；`workflow.md` 无 >1200 字行；`progress.md` 无"本轮相关变更范围"；`CHANGELOG.md` 存在；两 `plugin.json` description/version 已更新；`epi-linkage.md` 指向 PRW `wiki-writing-standard.md`。

- [ ] **Step 4: 最终 commit（若有 progress 验证段补登）**

```bash
git add -A
git commit -m "docs(epi): record S3a verification run in progress.md

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**1. Spec coverage（S3a 项 → 任务）：** E1→T1 ✓｜D3→T2 ✓｜C4→T3 ✓｜A3→T4 ✓｜A1→T5 ✓｜A2→T6 ✓｜A4→T7 ✓｜A5→T8 ✓｜C3→T9 ✓｜版本+验证→T10/T11 ✓。S3a 全部 9 项有任务覆盖。C2/C1（S3b）、B1/B2/B3（S2）已明确排除。

**2. Placeholder scan：** 无 TBD/TODO；每个测试给出完整可运行函数，每个文档编辑给出具体保留/删除/插入文本与要保的既有断言；命令均可直接跑。`overview.zh` 删除范围用"约行 41–319"——执行时以实际 `## 工作流总链路` 章节边界为准（`_section` 风格），非占位。

**3. Type/名称一致性：** 测试统一用各文件既有 helper（`_read`/`DOCS`/`PLUGIN_ROOT`、PRW `PLUGIN`/`PUBLIC_SKILL`）；新测试函数名互不冲突；版本串统一 `0.2.1` / `v0.2.1`；canonical 指针统一 `plugins/PRW/rules/wiki-writing-standard.md`。

**风险（已在 spec §7 记录）：** S2 若移动 PRW `rules/` 路径，需更新 T8 建立的 `rules/wiki-writing-standard.md` 指针——S2 plan 须显式回填。

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-07-epi-prw-s3a-doc-canonicalization.md`. 两种执行方式：

1. **Subagent-Driven（推荐）** — 每个 Task 派新 subagent，任务间两阶段复审，迭代快。
2. **Inline Execution** — 本会话内按 batch 执行，带 checkpoint 复审。
