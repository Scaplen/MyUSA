#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from health import check_nws_health, classify_engine
from current_conditions import current_conditions

API_ROOT = "https://api.weather.gov"
USER_AGENT = "MyUSA.us weather engine (https://myusa.us)"
RETRYABLE_HTTP = {408, 425, 429, 500, 502, 503, 504}
DEFAULT_MAX_STALE_SECONDS = 6 * 3600


class WeatherEngine:
    def __init__(
        self,
        cache_dir: str = ".cache/myusa-weather",
        timeout: int = 12,
        retries: int = 2,
        max_stale_seconds: int = DEFAULT_MAX_STALE_SECONDS,
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.retries = max(0, int(retries))
        self.max_stale_seconds = max(0, int(max_stale_seconds))

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{urllib.parse.quote(key, safe='')}.json"

    def _read_cache(self, key: str) -> dict[str, Any] | None:
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or "savedAt" not in payload or "payload" not in payload:
                return None
            return payload
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return None

    def _write_cache(self, key: str, payload: Any) -> dict[str, Any]:
        wrapper = {"savedAt": int(time.time()), "payload": payload}
        path = self._cache_path(key)
        tmp_path = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
        tmp_path.write_text(json.dumps(wrapper, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp_path, path)
        return wrapper

    @staticmethod
    def _cache_age(cached: dict[str, Any], now: int) -> int:
        return max(0, now - int(cached.get("savedAt", 0) or 0))

    def _fetch_upstream_json(self, url: str) -> tuple[Any, dict[str, Any]]:
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            started = time.monotonic()
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/geo+json, application/json",
                    "Cache-Control": "no-cache",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    payload = json.load(resp)
                    status = getattr(resp, "status", 200)
                return payload, {
                    "statusCode": status,
                    "latencyMs": round((time.monotonic() - started) * 1000),
                    "attempts": attempt + 1,
                }
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code not in RETRYABLE_HTTP or attempt >= self.retries:
                    break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt >= self.retries:
                    break

            # Short jittered exponential backoff keeps transient NWS failures from becoming user failures.
            delay = min(1.5, 0.20 * (2**attempt)) + random.uniform(0.0, 0.12)
            time.sleep(delay)

        assert last_error is not None
        raise last_error

    def _fetch_json(
        self,
        url: str,
        cache_key: str,
        ttl_seconds: int,
        max_stale_seconds: int | None = None,
    ):
        cached = self._read_cache(cache_key)
        now = int(time.time())
        stale_limit = self.max_stale_seconds if max_stale_seconds is None else max(0, int(max_stale_seconds))

        if cached:
            age = self._cache_age(cached, now)
            if age <= ttl_seconds:
                return cached["payload"], {"cache": "fresh", "stale": False, "ageSeconds": age}

        try:
            payload, upstream_meta = self._fetch_upstream_json(url)
            self._write_cache(cache_key, payload)
            return payload, {
                "cache": "refreshed",
                "stale": False,
                "ageSeconds": 0,
                **upstream_meta,
            }
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            if cached:
                age = self._cache_age(cached, now)
                if age <= stale_limit:
                    return cached["payload"], {
                        "cache": "last-known-good",
                        "stale": True,
                        "ageSeconds": age,
                        "maxStaleSeconds": stale_limit,
                        "upstreamError": str(exc),
                    }
            raise

    def point_metadata(self, lat, lon):
        lat = round(float(lat), 4)
        lon = round(float(lon), 4)
        return self._fetch_json(
            f"{API_ROOT}/points/{lat},{lon}",
            f"point:{lat},{lon}",
            86400,
            max_stale_seconds=7 * 86400,
        )

    def forecast_bundle(self, lat, lon):
        started = time.monotonic()
        lat = round(float(lat), 4)
        lon = round(float(lon), 4)

        point, point_meta = self.point_metadata(lat, lon)
        props = point.get("properties", {})
        forecast_url = props.get("forecast")
        hourly_url = props.get("forecastHourly")
        if not forecast_url or not hourly_url:
            raise RuntimeError("NWS point response did not include forecast endpoints")

        forecast, forecast_meta = self._fetch_json(
            forecast_url,
            f"forecast:{forecast_url}",
            900,
            max_stale_seconds=6 * 3600,
        )
        hourly, hourly_meta = self._fetch_json(
            hourly_url,
            f"hourly:{hourly_url}",
            600,
            max_stale_seconds=3 * 3600,
        )
        alerts, alerts_meta = self._fetch_json(
            f"{API_ROOT}/alerts/active?point={lat},{lon}",
            f"alerts:{lat},{lon}",
            60,
            max_stale_seconds=15 * 60,
        )
        observations = current_conditions(self, point)

        sources = (point_meta, forecast_meta, hourly_meta, alerts_meta)
        engine_meta = {
            "source": "National Weather Service / api.weather.gov",
            "point": point_meta,
            "forecast": forecast_meta,
            "hourly": hourly_meta,
            "alerts": alerts_meta,
            "usedFallback": any(m.get("stale") for m in sources),
            "requestDurationMs": round((time.monotonic() - started) * 1000),
        }
        engine_meta["health"] = classify_engine(
            engine_meta,
            check_nws_health(timeout=min(self.timeout, 5)),
        )

        return {
            "location": {
                "latitude": lat,
                "longitude": lon,
                "office": props.get("gridId"),
                "gridX": props.get("gridX"),
                "gridY": props.get("gridY"),
                "city": (props.get("relativeLocation") or {}).get("properties", {}).get("city"),
                "state": (props.get("relativeLocation") or {}).get("properties", {}).get("state"),
            },
            "current": observations,
            "forecast": forecast,
            "hourly": hourly,
            "alerts": alerts,
            "engine": engine_meta,
        }


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("lat", type=float)
    p.add_argument("lon", type=float)
    a = p.parse_args()
    print(json.dumps(WeatherEngine().forecast_bundle(a.lat, a.lon), indent=2))
