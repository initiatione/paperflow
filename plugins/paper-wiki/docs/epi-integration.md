# Paper Source / EPI Integration

Paper Wiki (formerly PRW, machine-facing name `paper-wiki`; `prw` is a pre-Stage-2 legacy alias) consumes Paper Source (formerly EPI, machine-facing name `paper-source`; `epi` is a pre-Stage-2 legacy alias) handoff artifacts and does not replace Paper Source.

Paper Wiki/PRW owns the wiki-side closed loop: read vault state, consume Paper Source/EPI handoff artifacts, write or repair formal pages, update tracking files, refresh `final-source-review.json`, run post-task checks, and report whether the paper is ready for EPI recording.

Paper Source/EPI owns paper discovery, ranking, download, MinerU parsing, paper wiki vault bootstrap through EPI `wiki-setup`, `paper-gate`, human approval, and `record-wiki-ingest`.

Paper Wiki/PRW assumes an initialized vault contract. It may check for the core `_epi` bootstrap (`_epi/`, `_epi/raw/`, `_epi/staging/`, `_epi/meta/`, `_epi/policies/`), `_meta/`, `.obsidian`, `.git`, and the seven formal page roots, but it does not initialize the vault, does not reset the vault, and does not silently create missing vault structure. If missing core vault structure blocks paper wiki work, report the capability gap and point the user back to EPI `wiki-setup`. Missing `_epi/runs/`, `_epi/cache/`, `_epi/tmp/`, `_epi/tmp-manual-pdfs/`, `_epi/quarantine/`, or `_epi/evolution/` is not a bootstrap failure; EPI creates those directories on demand.

The canonical EPI-to-PRW handoff is `wiki-ingest-brief.json`. Required inputs include the brief, reading report, metadata, PDF, MinerU Markdown, TeX, images, and manifest. `wiki_deposition_task.json` is a legacy compatibility artifact; Paper Wiki/PRW may read it for historical context, but task-only legacy handoffs are not ready for formal writes until EPI regenerates or repairs the brief. This canonical handoff / legacy compatibility split applies to new PRW intake.

If source artifacts are missing, stop and send the user back to EPI `paper-gate`. Human approval remains an EPI record; this plugin must not write human approval state. After formal pages are written and `final-source-review.json` exists, EPI `record-wiki-ingest` records final paths and hashes.

Paper Wiki/PRW may read previous `wiki-ingest-record.json` files to find affected formal pages, hashes, and reverse dependencies, but it must not refresh or replace those EPI record files. PRW records readiness; EPI writes or replaces `wiki-ingest-record.json` through `record-wiki-ingest`.

The read-only `ask_wiki` route is different from record-request ask-mode automation. `ask-wiki` answers user questions from the formal Obsidian graph, labels evidence/synthesis/inference/uncertainty, reports correction candidates, and asks before repair. It is the conversational primary entrypoint; EPI `wiki-ask` CLI is the same-source fallback / 程序化 `--json` entry. It does not write `log.md`, does not write formal pages, does not refresh QMD, does not write EPI artifacts, and ask-wiki does not write `prw-record-request.json`.

Ask-mode automation uses `_epi/staging/papers/<paper-slug>/prw-record-request.json`. PRW writes the request artifact; EPI consumes it. The request uses `schema_version: prw-record-request-v1`, `automation_mode: ask`, final page paths and sha256 hashes, `final-source-review.json` path/hash, and the human approval identity. The next EPI command is `record-wiki-ingest --from-prw-request _epi/staging/papers/<paper-slug>/prw-record-request.json`; EPI validates the live vault again before writing or replacing `wiki-ingest-record.json`.
