# EPI Integration

Paper Research Wiki consumes EPI handoff artifacts and does not replace EPI.

PRW owns the wiki-side closed loop: read vault state, consume EPI handoff artifacts, write or repair formal pages, update tracking files, refresh `final-source-review.json`, run post-task checks, and report whether the paper is ready for EPI recording.

EPI owns paper discovery, ranking, download, MinerU parsing, paper wiki vault bootstrap through EPI `wiki-setup`, `paper-gate`, human approval, and `record-wiki-ingest`.

PRW assumes an initialized vault contract. It may check for `_epi/`, `_meta/`, `.obsidian`, `.git`, and the seven formal page roots, but it does not initialize the vault, does not reset the vault, and does not silently create missing vault structure. If missing vault structure blocks paper wiki work, report the gap and point the user back to EPI `wiki-setup`.

Required inputs include `wiki_deposition_task.json`, `wiki-ingest-brief.json`, reading report, metadata, PDF, MinerU Markdown, TeX, images, and manifest.

If source artifacts are missing, stop and send the user back to EPI `paper-gate`. Human approval remains an EPI record; this plugin must not write human approval state. After formal pages are written and `final-source-review.json` exists, EPI `record-wiki-ingest` records final paths and hashes.
