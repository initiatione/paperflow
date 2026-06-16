# MinerU Precise Batch API Notes

Use the precise batch API for local PDFs:

- `POST /api/v4/file-urls/batch` to request upload URLs.
- `PUT` each PDF to its signed URL without a `Content-Type` header.
- `GET /api/v4/extract-results/batch/{batch_id}` until complete.
- Extract `full.md` and `images/` from `full_zip_url`.

Defaults: `model_version=vlm`, `language=en`, formulas and tables enabled, OCR disabled unless the paper is scanned.

Limits: up to 50 files per batch; each file must be <=200 MB and <=200 pages. Auth uses `Bearer <token>`; common token failures are `A0202` and `A0211`.

## CDN ZIP Recovery

If MinerU polling returns `state=done` but `full_zip_url` downloads fail with TLS EOF or similar CDN errors, check local DNS/proxy routing first. Clash/mihomo fake-IP setups can resolve `cdn-mineru.openxlab.org.cn` into `198.18.0.0/15`, then break the TLS connection.

Paper Source supports an explicit host/IP override for this case:

```powershell
$env:PAPER_SOURCE_MINERU_CDN_RESOLVE = "cdn-mineru.openxlab.org.cn=47.251.5.11"
```

The same setting can live in the MinerU env file loaded by runtime config. Multiple mappings may be separated by comma, semicolon, or whitespace. The downloader only applies a mapping when the ZIP URL host matches; it keeps the original HTTPS hostname and SNI, temporarily overriding DNS resolution for that request. Do not treat the example IP as permanent CDN configuration; refresh it with a trusted DNS lookup or fix the proxy DNS rule when possible.

When recovery succeeds, `mineru-manifest.json` includes `download_recovery.mode=host-ip-override`. When unset or unmatched, normal DNS behavior and the existing `download_failed` failure path remain unchanged.
