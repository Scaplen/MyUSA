#!/usr/bin/env python3
"""Freshness and health helpers for the MyUSA weather engine."""
from __future__ import annotations

import time
import urllib.error
import urllib.request
from typing import Any

NWS_HEALTH_URL = "https://api.weather.gov/health"
USER_AGENT = "MyUSA.us weather engine (https://myusa.us)"


def check_nws_health(timeout: int = 5) -> dict[str, Any]:
    req = urllib.request.Request(
        NWS_HEALTH_URL,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status_code = getattr(response, "status", 200)
            body = response.read().decode("utf-8", "replace")
        latency_ms = round((time.monotonic() - started) * 1000)
        return {
            "reachable": 200 <= status_code < 300,
            "statusCode": status_code,
            "latencyMs": latency_ms,
            "body": body[:500],
        }
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        return {
            "reachable": False,
            "statusCode": getattr(exc, "code", None),
            "latencyMs": round((time.monotonic() - started) * 1000),
            "error": str(exc),
        }


def classify_engine(engine_meta: dict[str, Any], nws_health: dict[str, Any] | None = None) -> dict[str, Any]:
    sources = [engine_meta.get(name) or {} for name in ("point", "forecast", "hourly", "alerts")]
    stale_sources = [name for name in ("point", "forecast", "hourly", "alerts") if (engine_meta.get(name) or {}).get("stale")]
    ages = [(src.get("ageSeconds") or 0) for src in sources if src.get("stale")]
    worst_age = max(ages) if ages else 0
    health_bad = nws_health is not None and not nws_health.get("reachable", False)

    if stale_sources and worst_age > 3600:
        status = "STALE"
    elif stale_sources or health_bad:
        status = "DEGRADED"
    else:
        caches = {src.get("cache") for src in sources if src}
        status = "CACHED" if caches and caches <= {"fresh"} else "LIVE"

    return {
        "status": status,
        "staleSources": stale_sources,
        "oldestFallbackAgeSeconds": worst_age or None,
        "nwsHealth": nws_health,
    }
