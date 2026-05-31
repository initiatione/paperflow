---
name: mineru-paper-parser
description: "Use when parsing local PDFs in EPI with MinerU into Markdown, TeX, images, and a manifest, or when validating the EPI steps 1-3 raw parse outputs."
---

# MinerU 论文解析

把 PDF 论文转成 AI 可轻松阅读的结构化产物：Markdown 全文、LaTeX 公式、独立图片资产和解析清单。

## 核心目标

解析的终极目的是**让下游 AI reader 能无障碍理解论文中的图片、公式和文字**：

- `paper.md` — 全文 Markdown，保留章节结构、表格、行内/行间公式（LaTeX 语法）。AI reader 的主要阅读入口。
- `paper.tex` — 完整 LaTeX 源码，保留原始公式排版。当 Markdown 中公式渲染不清时，reader 可回溯此文件获取精确公式。
- `images/` — 论文中所有图片（含图表、示意图、实验结果图）独立导出。AI reader 可直接引用图片路径进行多模态理解。
- `mineru-manifest.json` — 解析元数据：tex_source 类型、页数、图片数量、解析耗时。用于质量判断和故障排查。

这四个产物协同工作：文字靠 `paper.md`，公式靠 `paper.md` 内联 LaTeX + `paper.tex` 回溯，图片靠 `images/` 独立资产。缺任何一个都会降低 AI 阅读质量。

## 命令

### 在 EPI 链路中（推荐）

使用 orchestrator 封装，确保产物契约一致：

```powershell
python scripts\orchestrator.py parse-paper --slug <slug> --vault <vault>
```

### 独立批量解析

不经过 EPI 链路时，直接调用脚本：

```powershell
python skills/mineru-paper-parser/scripts/mineru_batch_to_md.py --input-dir paper --output-dir parsed
```

## 产物位置与清理

最终产物只存放在 `_raw\papers\<slug>\mineru\` 下：

```
_raw\papers\<slug>\mineru\
├── paper.md
├── paper.tex
├── images\...
└── mineru-manifest.json
```

成功解析后只保留日志：`mineru-command\stdout.txt` 和 `mineru-command\stderr.txt`。大体积工作副本（`mineru-command\paper`、`mineru-command\parsed`）应被清理，不应残留。

## LaTeX 回退机制

MinerU 默认使用 VLM 模型，公式和表格提取已开启。如果 MinerU 未返回原生 `.tex` 文件，EPI 会从 Markdown 衍生一份非空 LaTeX 回退版本：

- 原生 TeX → `tex_source=mineru-native`
- 衍生回退 → `tex_source=markdown-fallback`

两种情况都保证 `paper.tex` 非空，下游 reader 始终有公式回溯源。

## 失败排查

解析失败时，按以下顺序检查：

1. `parse-record.json` — 解析状态和错误码
2. `mineru-command\stdout.txt` — MinerU 标准输出
3. `mineru-command\stderr.txt` — MinerU 错误输出

常见问题：

- **`MinerU reported done but produced no Markdown output`** — 上游任务完成但 EPI 找不到 `paper.md`。保留 `mineru-command\paper` 和 `mineru-command\parsed` 用于诊断，然后重跑 `parse-paper` 或用 `redo-parse` 修复。
- **Token 错误 `A0202` / `A0211`** — 认证失败，检查 `MINERU_TOKEN` 是否过期。

## 安全与凭证

- Token 从 `MINERU_TOKEN` 环境变量或 `.env/mineru.env` 读取。
- 不打印、不持久化 token 明文。
- API 限制：每批最多 50 文件，单文件 ≤200MB / ≤200 页。
- 详细 API 说明见 `references/mineru_api.md`。
