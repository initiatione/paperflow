# PRW EPI Ask Record Automation Design

## Goal

Automate the final EPI record step after PRW writes formal paper wiki pages, while keeping EPI as the only owner of `wiki-ingest-record.json` writes.

## Architecture

PRW remains the user-facing formal wiki writing and maintenance layer. After a successful formal write or repair, PRW creates `_epi/staging/papers/<slug>/prw-record-request.json` with the final page paths, page hashes, `final-source-review.json` path/hash, human approval identity, and the recommended EPI record command.

EPI owns the record executor. `record-wiki-ingest` accepts `--from-prw-request <path>` and validates the request against the live vault before writing `_epi/raw/<slug>/wiki-ingest-record.json` and `_epi/staging/papers/<slug>/wiki-ingest-record.json`.

## Default Mode

The default automation mode is `ask`. PRW does not silently write EPI records. It reports that the request is ready and, when the current agent/user has asked to complete the chain, the agent can continue by invoking EPI with the request path.

Supported request modes:

- `ask`: default; safe handoff plus agent/user confirmation.
- `off`: report the command only.
- `on`: future explicit opt-in; only valid when all gates pass and no staged patch, missing approval, hash drift, ambiguous merge, or destructive action is present.

## Request Contract

Schema version: `prw-record-request-v1`.

Required fields:

- `paper_slug`: EPI paper slug.
- `status`: `ready_for_epi_record`.
- `automation_mode`: normally `ask`.
- `final_pages[]`: each item has `relative_path` and `sha256`.
- `final_source_review.path` and `final_source_review.sha256`.
- `human_approval.approved_by`.

Optional fields:

- `request_id`: stable id from slug plus page/review hashes.
- `correction_id`: for repaired premature records.
- `recommended_command`: display command for handoff reports.
- `prw_task`: workflow metadata.

## Validation

EPI must reject the request before writing records when:

- schema or status is unsupported;
- slug is missing or mismatched;
- final page paths are outside the vault or under internal roots;
- page hashes in the request do not match the current formal pages;
- `final-source-review.json` is missing or its hash changed;
- human approval is missing or `approved_by` does not match;
- the normal `paper-gate` / formal page / final source review checks fail.

## Recovery

A failed record attempt must not roll back formal pages. The request artifact remains in staging, and EPI reports the blocker. Re-running the same valid request is safe because EPI recomputes live hashes and records the source request metadata in the resulting wiki ingest record.

