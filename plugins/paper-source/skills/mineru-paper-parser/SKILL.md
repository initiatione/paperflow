---
name: mineru-paper-parser
description: >
  Use when parsing papers with MinerU: "MinerU 解析", PDF 转 Markdown, parse-paper, TeX/images/manifest,
  figure/formula indexes, normalize-mineru-assets.
---

# MinerU Paper Parser

Parse local PDFs into Paper Source raw artifacts: Markdown, optional native TeX/formulas, images, figure/formula indexes, and parse metadata.

## Output Contract

Final outputs live only under `_paper_source\\raw\\<slug>\mineru\` plus raw sidecars:

```text
_paper_source\\raw\\<slug>\mineru\ (<slug>.md, optional paper.tex, images\..., mineru-manifest.json)
_paper_source\\raw\\<slug>\ (figure-index.json, formula-index.json, asset-normalization-record.json)
```

`<slug>.md` is the main reader surface; `paper.md` is legacy fallback only. `paper.tex` exists only when MinerU returns non-empty native TeX. Successful parses keep only `mineru-command\stdout.txt` and `mineru-command\stderr.txt`; `mineru-command\paper` and `mineru-command\parsed` should not remain after success.

## Commands

Prefer the orchestrator:

```powershell
python scripts\orchestrator.py parse-paper --slug <slug> --vault <vault>
python scripts\orchestrator.py normalize-mineru-assets --slug <slug> --vault <vault> --json
python scripts\orchestrator.py normalize-mineru-assets --slug <slug> --vault <vault> --execute --json
```

Use `--mineru-timeout <seconds>` for one-off runs. If omitted, Paper Source reads `PAPER_SOURCE_MINERU_TIMEOUT`; invalid/non-positive values fall back to 7200 seconds.

`normalize-mineru-assets` may read `_paper_source/raw/<slug>` or legacy `_epi/raw/<slug>` and may change raw image names, Markdown image references, and index sidecars. It must not edit formal wiki pages.

Standalone batch path:

```powershell
python skills/mineru-paper-parser/scripts/mineru_batch_to_md.py --input-dir paper --output-dir parsed
```

## TeX And Failures

- Native TeX records `tex_source=mineru-native`; Markdown-only success records `tex_source=paused-no-native-tex` and does not synthesize `paper.tex`.
- New parses normalize figures to stable `fig-###-*`; ambiguous images stay reviewable as `unmapped-*`.
- Formula screenshots with Markdown/TeX LaTeX evidence move out of preserved figures and into `formula-index.json`; Markdown/TeX formulas must remain complete.
- On failure, inspect `parse-record.json`, `mineru-command\stdout.txt`, then `mineru-command\stderr.txt`.
- `MinerU reported done but produced no Markdown output` means no usable Markdown was found for `mineru\<slug>.md`; keep work folders, then rerun `parse-paper` or repair with `redo-parse`.
- `MinerU output download failed` with a `download_failed` manifest entry means MinerU finished extraction but Paper Source could not fetch the output ZIP, commonly because of transient MinerU CDN/SSL/network failures. Rerun `parse-paper`; the bundled downloader retries transient ZIP failures before recording the final error.
- Token errors such as `A0202` or `A0211` usually mean authentication failed.

Read tokens from `MINERU_TOKEN` or `.env/mineru.env`. Never print or persist token values. MinerU API details live in `references/mineru_api.md`.
