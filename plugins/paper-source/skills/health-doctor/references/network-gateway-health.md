# Network And Gateway Health

Use this reference when Paper Source or `grok-search-rs` reaches an OpenAI-compatible/Grok upstream but receives 403, Cloudflare challenge HTML, non-JSON responses, timeouts, TLS errors, DNS failures, or model fallback loops.

## Safe Probe

Run a metadata-only probe first:

```powershell
python skills\health-doctor\scripts\openai_compatible_probe.py --base-url <url> --api-key-env OPENAI_COMPATIBLE_API_KEY
```

Add `--chat --model <model>` only when the user agrees to a tiny completion request and the endpoint may incur cost.

## Failure Classes

- `config_missing`: base URL, key, or model was not supplied.
- `connection_error`: DNS, proxy, route, firewall, service down, or wrong host.
- `tls_error`: certificate, SNI, MITM proxy, fake-IP, or HTTPS interception issue.
- `timeout`: upstream reachable path is too slow or blocked.
- `cloudflare_challenge`: 403 plus Cloudflare/challenge HTML or headers; usually a browser-protection page, not an API JSON response.
- `auth_error_or_forbidden`: 401/403 JSON or provider-level forbidden response; check key, account, model entitlement, allowed IP, and route policy.
- `non_json`: a reverse proxy, login page, CDN error page, or HTML challenge answered an API path.
- `rate_limited`: provider quota or throttling.
- `upstream_error`: provider-side 5xx or gateway failure.

## Cloudflare 403 Handling

For OpenAI-compatible upstreams blocked by Cloudflare, do not hardcode a local bypass or private relay into Paper Source. Diagnose generically:

1. Confirm the base URL is a real server-to-server API route, not a browser page.
2. Check whether `/v1/models` returns JSON with the same key outside Codex from the same network.
3. Verify proxy/TUN/fake-IP/DNS rules route the API host as intended.
4. Ask the upstream owner to allow API clients, disable browser challenges for API paths, or provide a challenge-free API hostname.
5. Keep endpoint, key, cookie, token, and local proxy details in user runtime config or env files only.

Paper Source can record that the class is `cloudflare_challenge` or `non_json`, but it should not ship private hostnames, cookies, challenge tokens, IP rules, or subscription details.

## Grok/OpenAI-Compatible Runtime

Grok supplemental discovery uses the user's configured OpenAI-compatible URL/key/model through `grok-search-rs` or equivalent runtime. The plugin should surface:

- base URL presence, not secret endpoint policy;
- key set/missing, never the key;
- selected model and configured fallbacks;
- whether provider fallback consumed the timeout budget;
- whether no contribution came from provider/runtime failure, timeout, parser/normalization, weak identity, or downstream filtering.

Do not reinterpret provider/network failure as evidence that the research topic has no papers.

