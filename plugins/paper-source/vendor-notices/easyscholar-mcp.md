# EasyScholar MCP Vendor Notice

EPI's EasyScholar quality enrichment is based on the API integration pattern from `chaosman42/easyscholar-mcp`.

- Upstream: https://github.com/chaosman42/easyscholar-mcp
- License: MIT License
- Upstream copyright: Copyright (c) 2026 chaosman42

EPI ports the EasyScholar publication-rank request and result-field interpretation into native Python so discovery can write `easyscholar-record.json`, `verified_metrics.easyscholar`, and `easyscholar_score` without launching a nested Node MCP server.

The integration uses `EASYSCHOLAR_SECRET_KEY` from the process environment or an approved runtime env file. Secrets must never be written to reports, cache records, logs, or git-tracked config. If the key is missing, the default-on enrichment soft-fails and downstream output must mark metrics as `未核实`.
