---
name: mineru-paper-parser
description: "Use when parsing local PDFs in EPI with MinerU into Markdown, TeX, images, and a manifest."
---

# Mineru Precision Batch

Parse local PDF batches through MinerU's precise batch API and save each result as Markdown, LaTeX, images, and a manifest.

```powershell
python skills/mineru-paper-parser/scripts/mineru_batch_to_md.py --input-dir paper --output-dir parsed
```

Use relative paths when practical. Read the token from `MINERU_TOKEN` or `.env/mineru.env`; never print or persist tokens.

For batch reuse, layout choices, API details, and limits, read `references/mineru_api.md`.
