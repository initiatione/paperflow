---
name: mineru-paper-parser
description: "Use when parsing local PDFs in EPI with MinerU into Markdown, TeX, images, and a manifest, or when validating the EPI steps 1-3 raw parse outputs."
---

# Mineru Precision Batch

Parse local PDFs with MinerU and save Markdown, LaTeX, images, and manifest outputs.

```powershell
python skills/mineru-paper-parser/scripts/mineru_batch_to_md.py --input-dir paper --output-dir parsed
```

In EPI paper roots, prefer the orchestrator wrapper so the final artifact contract is consistent:

```powershell
python scripts\orchestrator.py parse-paper --slug <slug> --vault D:\paper-research-wiki
```

Final outputs belong only under `_raw\papers\<slug>\mineru\`: `paper.md`, `paper.tex`, `images\...`, and `mineru-manifest.json`. Successful parses keep only `mineru-command\stdout.txt` and `mineru-command\stderr.txt` as logs; large work copies under `mineru-command\paper` and `mineru-command\parsed` should not remain. If MinerU returns no native `.tex`, EPI writes a non-empty Markdown-derived LaTeX fallback and records `tex_source=markdown-fallback`; native TeX records `tex_source=mineru-native`.

Read tokens from `MINERU_TOKEN` or `.env/mineru.env`; never print or persist tokens. For API details and limits, read `references/mineru_api.md`.
