# EPI/PRW Changelog

## 0.2.1 (2026-06-07)

- S3a 文档/契约 canonical 化：A1 overview 导航化。
- A2 workflow 巨段拆成短入口。
- A3 doc map 收敛到 `docs/epi-linkage.md`。
- A4 progress 快照化，历史迁入本文件。
- A5 page-family/frontmatter 人读 canonical 指向 PRW `rules/wiki-writing-standard.md`。
- C3 只读问答归属：PRW `ask_wiki` 是对话主入口，EPI `wiki-ask` 是同源 fallback / 程序化入口。
- C4 `wiki-ingest-brief.json` 是 canonical handoff；`wiki_deposition_task.json` 是 deprecated 兼容 artifact。
- D3 删除 `_write_json` 私有别名，直接调用 `write_json_atomic`。
- E1 EPI plugin description 改为 discovery -> MinerU -> critic -> wiki handoff 全链路定位。

## 0.2.0 (2026-06-07)

- 增加 read-only formal graph `wiki-ask`。
- PRW ask-mode record automation 写 `prw-record-request.json`。
- EPI `record-wiki-ingest --from-prw-request` 消费 PRW request artifact。
- Source manifest 同步到 EPI `0.2.0` / PRW `0.2.0`。

## 0.1.14 / 0.1.7

- PRW -> EPI ask-mode record automation。
- `automation_mode=ask` 与 live page hash 验证。
- `final-source-review.json` 与 human approval identity 一起进入 record gate。

## 0.1.13 / 0.1.6

- Workflow boundary source version sync。
- 明确 PRW `$paper-research-wiki` 与 EPI `epi-paper-deposition` compatibility adapter 边界。
- 更新 formal page gate 与 record provenance 说明。

## Earlier 0.1.x Notes

- Runtime 配置进入用户级 `runtime.json`。
- `paper-search` MCP/CLI fallback、provider readiness 和 MinerU env file 分层。
- `prepare-ranked --skip-existing` 防止补跑时已解析论文占用预算。
- `paper-quality-critic`、`parse-quality-critic` 和 role critic quorum 进入 audited ingest。
- `run-lifecycle` 与 bounded lifecycle cleanup 加入默认维护边界。
- Plugin Eval 历史信号包含 pass rate `1` 和 `82/100`；这些是历史快照，发布前必须重跑。
