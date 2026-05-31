---
name: paper-ingest
description: "Use when ingesting selected papers into EPI raw artifacts, or continuing beyond MinerU parse into readers, critics, and staging drafts."
---

# Paper Ingest

在 dry-run 排序选出候选论文后，把它们摄取进 EPI 流水线。整条链路的目标（见 `docs\epi-linkage.md`）：

**高质量论文采集 → LLM Wiki 知识沉淀 → 低负担阅读报告。**

配置缺失时**停止 ingest**，转用 `config-setup`。配置 onboarding 在 `docs\config.md` 的 `## 聊天式初始化脚本`——按脚本走，不要自由发挥成技术字段问卷，也不要一次性输出完整默认配置。

## 两条路径：先认清用户要走多远

这个 skill 跨越了链路的两段。用错命令会让用户"只想下载"却被推进到 critic/staging，所以先判断意图：

| 用户意图 | 用哪条路径 |
| --- | --- |
| 只要 steps 1-3（下载 + MinerU 解析，停在 raw） | **路径 A：prepare-ranked** |
| 继续进入 reader → critic → staging 沉淀 | **路径 B：advance + gate + handoff** |

## 路径 A：steps 1-3（只到 raw artifact）

下载选中论文并用 MinerU 解析，停在 `mineru\paper.md`、`mineru\paper.tex`、`mineru\images`、`mineru\mineru-manifest.json`：

```powershell
python scripts\orchestrator.py prepare-ranked --run-id <dry-run-id> --max-papers 10 --skip-existing --include-review-candidates --vault <vault>
python scripts\orchestrator.py prepare-ranked --run-id <dry-run-id> --max-papers 10 --skip-existing --include-review-candidates --vault <vault> --json
python scripts\orchestrator.py prepare-ranked --run-id <dry-run-id> --max-papers 1 --vault <vault>
```

- 实测批量用 `--max-papers 10 --skip-existing`，避免已解析论文消耗 batch 配额。
- `--max-papers 1` **只是 smoke test**，不要用于正式跑。
- 串联自动化时加 `--json`，读取 prepared run id、processed/skipped counts、stop point 和报告路径。
- `prepare-ranked` 会记录每篇的 `acquire_failed` / `parse_failed` / `prepare_failed` 并继续——检查报告，不要因为非零退出码就假设全部失败。
- Do not use `advance-paper`, `advance-ranked`, or `advance-batch` when the user only asked for 1-3. **用户只要 1-3 时，不要用** `advance-paper` / `advance-ranked` / `advance-batch`，因为这些命令会在后续调用中继续推进到 reader/critic/staging。

## 路径 B：继续到 reader → critic → staging

```powershell
python scripts\orchestrator.py advance-ranked --run-id <dry-run-id> --max-papers 3 --vault <vault>
python scripts\orchestrator.py advance-batch --candidates <candidate-json> --max-papers 3 --vault <vault>
python scripts\orchestrator.py paper-gate --slug <slug> --vault <vault>
python scripts\orchestrator.py wiki-ingest-handoff --slug <slug> --vault <vault>
python scripts\orchestrator.py research-queue --bucket needs_reader_repair --vault <vault>
python scripts\orchestrator.py research-queue --bucket reproducibility_caveats --actions --json --vault <vault>
```

critic 通过后，staging 会准备：evidence drafts、`wiki-ingest-brief.json`、`reports/<slug>-reading-report.md`（低负担阅读报告）。

## 阅读报告应突出什么

低负担阅读报告是给人和下游 AI 快速理解论文用的，应聚焦：

- 理论洞见（theory insight）
- 实验设计（experiment design）
- Reading Trust Status（阅读可信状态）
- 证据强度（evidence strength）
- 建议的 wiki 路由（suggested wiki routes）
- 紧凑的可复现性注意事项（reproducibility caveats）

## Wiki 沉淀的边界与契约

最终 Obsidian / LLM Wiki 页面由 agent 按**目标 vault 契约**创建，**不是**由 EPI staging 或本地 `llm-wiki` / `wiki-ingest` skill 固定。写入前：

1. 解析目标 vault 的 `AGENTS.md` 和 `_meta/*`。
2. 框架参考：Ar9av/obsidian-wiki、kepano/obsidian-skills、initiatione/obsidian-wiki-dev 的 `liuchf/wiki-skills`。
3. 把本地 `llm-wiki`、`wiki-ingest`、`obsidian-markdown` 当作**执行适配器**，不是规则来源。
4. `wiki-ingest-brief.json` 必须携带 `wiki_rule_source_model`，让接收方 agent 在写入前看到规则优先级。
5. 用 `wiki-ingest-handoff` 渲染只读 agent checklist 和目标 vault 契约状态，再做最终 wiki ingest。

## 安全边界

- raw / staging 写入：**允许**。
- compiled wiki 写入：**不允许**——没有 critic pass、没有 wiki ingest handoff 时，不写最终 wiki。
