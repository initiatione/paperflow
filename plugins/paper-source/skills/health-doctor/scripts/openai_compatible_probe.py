#!/usr/bin/env python3
"""Probe an OpenAI-compatible endpoint without printing API keys."""

from __future__ import annotations

import argparse
import json
import os
import socket
import ssl
import urllib.error
import urllib.request
from typing import Any, Dict, Tuple


def normalize_base_url(raw: str) -> str:
    base = raw.rstrip("/")
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    return base


def response_snippet(body: bytes, limit: int = 300) -> str:
    text = body[:limit].decode("utf-8", errors="replace")
    return " ".join(text.split())


def looks_like_cloudflare(status: int | None, headers: Dict[str, str], body: bytes) -> bool:
    lower_headers = {key.lower(): value.lower() for key, value in headers.items()}
    body_l = body[:4096].lower()
    return bool(
        status == 403
        and (
            "cloudflare" in lower_headers.get("server", "")
            or "cf-ray" in lower_headers
            or b"cloudflare" in body_l
            or b"cf-error" in body_l
            or b"just a moment" in body_l
            or b"attention required" in body_l
        )
    )


def classify_http(status: int, headers: Dict[str, str], body: bytes) -> Tuple[str, Dict[str, Any]]:
    content_type = headers.get("content-type", "")
    details: Dict[str, Any] = {
        "status_code": status,
        "content_type": content_type,
        "server": headers.get("server"),
        "cf_ray_present": "cf-ray" in {key.lower() for key in headers},
    }

    if looks_like_cloudflare(status, headers, body):
        details["snippet"] = response_snippet(body)
        return "cloudflare_challenge", details

    parsed = None
    if body:
        try:
            parsed = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            details["snippet"] = response_snippet(body)

    if status in {401, 403}:
        if parsed and isinstance(parsed, dict):
            details["error"] = parsed.get("error", parsed)
        return "auth_error_or_forbidden", details
    if status == 429:
        return "rate_limited", details
    if status >= 500:
        return "upstream_error", details
    if parsed is None and "json" not in content_type.lower():
        return "non_json", details
    if parsed is not None:
        if isinstance(parsed, dict) and isinstance(parsed.get("data"), list):
            details["model_count"] = len(parsed["data"])
            details["sample_models"] = [
                item.get("id")
                for item in parsed["data"][:5]
                if isinstance(item, dict) and item.get("id")
            ]
        return "ok_json", details
    return "ok_non_json", details


def request(
    method: str,
    url: str,
    api_key: str | None,
    timeout: float,
    payload: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    headers = {"accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["content-type"] = "application/json"
    if api_key:
        headers["authorization"] = "Bearer <redacted>"
    real_headers = dict(headers)
    if api_key:
        real_headers["authorization"] = f"Bearer {api_key}"

    redacted_headers = {key: value for key, value in headers.items()}
    req = urllib.request.Request(url, data=data, headers=real_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(65536)
            headers_dict = {key.lower(): value for key, value in resp.headers.items()}
            classification, details = classify_http(resp.status, headers_dict, body)
            return {
                "status": classification,
                "url": url,
                "method": method,
                "request_headers": redacted_headers,
                "details": details,
            }
    except urllib.error.HTTPError as exc:
        body = exc.read(65536)
        headers_dict = {key.lower(): value for key, value in exc.headers.items()}
        classification, details = classify_http(exc.code, headers_dict, body)
        return {
            "status": classification,
            "url": url,
            "method": method,
            "request_headers": redacted_headers,
            "details": details,
        }
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, socket.timeout):
            status = "timeout"
        elif isinstance(reason, ssl.SSLError):
            status = "tls_error"
        else:
            status = "connection_error"
        return {
            "status": status,
            "url": url,
            "method": method,
            "request_headers": redacted_headers,
            "details": {"reason": str(reason)},
        }
    except socket.timeout:
        return {
            "status": "timeout",
            "url": url,
            "method": method,
            "request_headers": redacted_headers,
            "details": {"reason": "socket timeout"},
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_COMPATIBLE_API_URL"))
    parser.add_argument("--api-key-env", default="OPENAI_COMPATIBLE_API_KEY")
    parser.add_argument("--api-key", default=None, help="API key value; omitted from output")
    parser.add_argument("--model", default=os.environ.get("OPENAI_COMPATIBLE_MODEL"))
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--chat", action="store_true", help="Also run a tiny chat completion probe")
    args = parser.parse_args()

    if not args.base_url:
        print(
            json.dumps(
                {
                    "schema": "paperflow-openai-compatible-probe-v1",
                    "status": "config_missing",
                    "missing": ["base_url"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    api_key = args.api_key or os.environ.get(args.api_key_env)
    base_url = normalize_base_url(args.base_url)
    checks = {
        "models": request("GET", f"{base_url}/models", api_key, args.timeout),
    }

    if args.chat:
        if not api_key:
            checks["chat_completions"] = {"status": "skipped", "reason": "api key missing"}
        elif not args.model:
            checks["chat_completions"] = {"status": "skipped", "reason": "model missing"}
        else:
            checks["chat_completions"] = request(
                "POST",
                f"{base_url}/chat/completions",
                api_key,
                args.timeout,
                {
                    "model": args.model,
                    "messages": [{"role": "user", "content": "Respond with ok."}],
                    "temperature": 0,
                    "max_tokens": 4,
                },
            )

    print(
        json.dumps(
            {
                "schema": "paperflow-openai-compatible-probe-v1",
                "base_url": base_url,
                "api_key_env": args.api_key_env,
                "api_key_status": "set" if api_key else "missing",
                "model": args.model,
                "checks": checks,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
