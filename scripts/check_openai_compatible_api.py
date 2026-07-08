#!/usr/bin/env python3
"""Small preflight check for OpenAI-compatible chat completion endpoints."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def endpoint(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    payload = {
        "model": args.model,
        "messages": [{"role": "user", "content": "ping"}],
        "temperature": 0,
        "max_tokens": 1,
    }
    req = urllib.request.Request(
        endpoint(args.base_url),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {args.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=args.timeout) as resp:
            body = resp.read(4096).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read(4096).decode("utf-8", errors="replace")
        print(
            f"API preflight failed: HTTP {exc.code} for model={args.model} at {endpoint(args.base_url)}",
            file=sys.stderr,
        )
        print(body, file=sys.stderr)
        return 1
    except Exception as exc:
        print(
            f"API preflight failed: {type(exc).__name__}: {exc} for model={args.model} at {endpoint(args.base_url)}",
            file=sys.stderr,
        )
        return 1

    try:
        parsed = json.loads(body)
    except Exception:
        parsed = {}
    if isinstance(parsed, dict) and parsed.get("error"):
        print(f"API preflight failed: endpoint returned error for model={args.model}", file=sys.stderr)
        print(json.dumps(parsed["error"], ensure_ascii=False), file=sys.stderr)
        return 1

    print(f"API preflight OK: model={args.model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
