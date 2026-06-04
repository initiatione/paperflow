# Paper Research Wiki Workflow

The plugin exposes one user-facing assistant for direct EPI paper deposition, wiki checks, wiki updates, and relink maintenance.

The ordinary path is: preflight EPI handoffs, identify ready papers, deposit them into staged or formal pages under the target vault contract, preserve provenance, write `final-source-review.json`, and return recording to EPI `record-wiki-ingest`.

EPI prepares source bundles and handoff artifacts. Paper Research Wiki reads them and performs the formal wiki-side work without taking over EPI discovery, MinerU parsing, paper-gate, human approval, or record-only completion.
