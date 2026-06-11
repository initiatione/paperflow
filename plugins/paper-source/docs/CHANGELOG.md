# Paper Source/Paper Wiki Changelog

## Unreleased

- S3b brief-first machine-contract 进入实现队列：`wiki-ingest-brief.json` 作为新链路 canonical handoff，`wiki_deposition_task.json` 降为 legacy compatibility，`REQUIRED_WIKI_SKILLS` 将收敛到 Paper Wiki `$paper-research-wiki` 和 Paper Source `paper-source-paper-deposition`。

## Paper Source 0.2.4 / Paper Wiki 0.2.3 (2026-06-11)

- Paper Source/Paper Wiki 合同统一为新正式页 `lifecycle: draft`，不再新增 `review_status`；旧 `lifecycle: review-needed` 只作为 legacy repair input。
- Frontmatter `sources` 改为 scan-friendly short labels；完整 `obsidian://` PDF 入口放入正文 `## 原文与证据入口`，正式 wikilink 不指向 `_paper_source/` 或 legacy `_epi/`。
- 公式和符号证据顺序改为 MinerU Markdown 主源；只有 Markdown 缺失、错误、歧义或不足时回退 PDF、figure/formula indexes 和图片证据，非空原生 `mineru/paper.tex` 仅作可选交叉复核。
- Paper Wiki 合同扩展为 formal page、正式内容关系、stale claim、split/merge、图谱/索引/追踪/provenance/readiness 维护层。

## 0.2.3 (2026-06-10)

- Paper Source skill trigger descriptions 再精炼：保留中文任务触发词、Paper Source/Paper Wiki 边界和 research-grill-me deep-research prompt 契约，降低默认触发上下文成本。

## 0.2.2 (2026-06-10)

- Paper Source / Paper Wiki skill 入口压缩：保留路由、来源边界、handoff gate 和 post-task check，减少默认加载成本。
- Paper Source / Paper Wiki manifest 和默认 prompt 精简为短入口，版本同步到 `0.2.2`。
- Paper Wiki 继续保持一个用户级 `$paper-research-wiki` 助手，`paper-wiki-language` 作为正式页语言 gate。

## 0.2.1 (2026-06-07)

- S3a 文档/契约 canonical 化：A1 overview 导航化。
- A2 workflow 巨段拆成短入口。
- A3 doc map 收敛到 `docs/paper-source-linkage.md`。
- A4 progress 快照化，历史迁入本文件。
- A5 page-family/frontmatter 人读 canonical 指向 Paper Wiki `rules/wiki-writing-standard.md`。
- C3 只读问答归属：Paper Wiki `ask_wiki` 是对话主入口，Paper Source `wiki-ask` 是同源 fallback / 程序化入口。
- C4 `wiki-ingest-brief.json` 是 canonical handoff；`wiki_deposition_task.json` 是 deprecated 兼容 artifact。
- D3 删除 `_write_json` 私有别名，直接调用 `write_json_atomic`。
- E1 Paper Source plugin description 改为 discovery -> MinerU -> critic -> wiki handoff 全链路定位。

## 0.2.0 (2026-06-07)

- 增加 read-only formal graph `wiki-ask`。
- Paper Wiki ask-mode record automation 写 `paper-wiki-record-request.json`。
- Paper Source `record-wiki-ingest --from-paper-wiki-request` 消费 Paper Wiki request artifact；legacy `prw-record-request.json` / `--from-prw-request` 仅用于既有 artifact 兼容。
- Source manifest 同步到 Paper Source `0.2.0` / Paper Wiki `0.2.0`。

## 0.1.14 / 0.1.7

- Paper Wiki -> Paper Source ask-mode record automation。
- `automation_mode=ask` 与 live page hash 验证。
- `final-source-review.json` 与 human approval identity 一起进入 record gate。

## 0.1.13 / 0.1.6

- Workflow boundary source version sync。
- 明确 Paper Wiki `$paper-research-wiki` 与 Paper Source `paper-source-paper-deposition` compatibility adapter 边界。
- 更新 formal page gate 与 record provenance 说明。

## Earlier 0.1.x Notes

- Runtime 配置进入用户级 `runtime.json`。
- `paper-search` MCP/CLI fallback、provider readiness 和 MinerU env file 分层。
- `prepare-ranked --skip-existing` 防止补跑时已解析论文占用预算。
- `paper-quality-critic`、`parse-quality-critic` 和 role critic quorum 进入 audited ingest。
- `run-lifecycle` 与 bounded lifecycle cleanup 加入默认维护边界。
- Plugin Eval 历史信号包含 pass rate `1` 和 `82/100`；这些是历史快照，发布前必须重跑。
