---
name: mineru-paper-parser
description: >
  Use when parsing local EPI PDFs with MinerU, including "MinerU 解析",
  "PDF 转 Markdown", parse-paper, TeX, images, and manifest generation.
---

# MinerU Paper Parser

Parse local PDFs into reader-ready EPI artifacts: Markdown text, TeX/formulas, extracted images, and parse metadata.

## Contract

Final outputs live only under `_epi\raw\papers\<slug>\mineru\`:

```text
_epi\raw\papers\<slug>\mineru\
|-- <slug>.md
|-- paper.tex
|-- images\...
`-- mineru-manifest.json
```

- `<slug>.md`: main reader surface. `paper.md` is accepted only as a legacy fallback from older vaults.
- `paper.tex`: formula/source fallback.
- `images/`: extracted figure assets.
- `mineru-manifest.json`: `tex_source`, page/image counts, timing.
- Successful parses keep only `mineru-command\stdout.txt` and `mineru-command\stderr.txt`; `mineru-command\paper` and `mineru-command\parsed` should not remain after success.

## Commands

Prefer EPI orchestrator:

```powershell
python scripts\orchestrator.py parse-paper --slug <slug> --vault <vault>
```

Use `--mineru-timeout <seconds>` for a one-off long or short run. If omitted, EPI reads `EPI_MINERU_TIMEOUT`; invalid or non-positive values fall back to 7200 seconds.

Standalone batch path:

```powershell
python skills/mineru-paper-parser/scripts/mineru_batch_to_md.py --input-dir paper --output-dir parsed
```

## TeX And Failures

- Native TeX records `tex_source=mineru-native`.
- Markdown fallback records `tex_source=markdown-fallback`; `paper.tex` should still be non-empty.
- On failure, inspect `parse-record.json`, `mineru-command\stdout.txt`, then `mineru-command\stderr.txt`.
- `MinerU reported done but produced no Markdown output` means the upstream job finished but EPI could not locate usable Markdown for `mineru\<slug>.md`; keep work folders for diagnosis, then rerun `parse-paper` or repair with `redo-parse`.
- Token errors such as `A0202` or `A0211` usually mean authentication failed.

Read tokens from `MINERU_TOKEN` or `.env/mineru.env`. Never print or persist token values. MinerU API details live in `references/mineru_api.md`.
