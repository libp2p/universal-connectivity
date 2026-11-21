#!/usr/bin/env python3
"""Container health check for the running py-peer API.

The peer's HTTP server can answer requests before the libp2p host is ready,
so an HTTP 200 alone is not a useful health signal. This check parses
``GET /api/v1/service/status`` and requires the runtime to report
``ready`` and ``running`` without a fatal ``failed`` flag.

Only the standard library is used: the image needs no curl or extra tools.
The URL can be overridden with ``UC_HEALTHCHECK_URL`` (for example when the
API port is changed).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

DEFAULT_URL = "http://127.0.0.1:8765/api/v1/service/status"
DEFAULT_TIMEOUT = 4.0


def check_health(url: str = DEFAULT_URL, timeout: float = DEFAULT_TIMEOUT) -> bool:
    """Return True only when the runtime reports ready and running."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.load(response)
    except Exception:
        return False

    data = payload.get("data") or {}
    if not isinstance(data, dict):
        return False
    return bool(data.get("ready")) and bool(data.get("running")) and not data.get("failed")


def main() -> int:
    url = os.environ.get("UC_HEALTHCHECK_URL", DEFAULT_URL)
    healthy = check_health(url)
    print("healthy" if healthy else "unhealthy")
    return 0 if healthy else 1


if __name__ == "__main__":
    sys.exit(main())
