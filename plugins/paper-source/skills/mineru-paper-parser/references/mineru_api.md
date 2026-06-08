# MinerU Precise Batch API Notes

Use the precise batch API for local PDFs:

- `POST /api/v4/file-urls/batch` to request upload URLs.
- `PUT` each PDF to its signed URL without a `Content-Type` header.
- `GET /api/v4/extract-results/batch/{batch_id}` until complete.
- Extract `full.md` and `images/` from `full_zip_url`.

Defaults: `model_version=vlm`, `language=en`, formulas and tables enabled, OCR disabled unless the paper is scanned.

Limits: up to 50 files per batch; each file must be <=200 MB and <=200 pages. Auth uses `Bearer <token>`; common token failures are `A0202` and `A0211`.
