#!/usr/bin/env python3
"""Current-condition intelligence from official NWS observation stations."""
from __future__ import annotations
import datetime as dt
from typing import Any


def _value(metric: Any):
    if not isinstance(metric, dict): return None
    value = metric.get("value")
    return float(value) if isinstance(value, (int, float)) else None


def c_to_f(value): return None if value is None else round(value * 9 / 5 + 32, 1)
def ms_to_mph(value): return None if value is None else round(value * 2.236936, 1)


def normalize_observation(payload: dict[str, Any], station_id: str | None = None) -> dict[str, Any]:
    p = payload.get("properties") or {}
    timestamp = p.get("timestamp")
    age_minutes = None
    if timestamp:
        try:
            observed = dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            age_minutes = max(0, round((dt.datetime.now(dt.timezone.utc) - observed).total_seconds() / 60))
        except ValueError: pass
    temp_c = _value(p.get("temperature")); dew_c = _value(p.get("dewpoint"))
    return {
        "station": station_id,
        "observedAt": timestamp,
        "ageMinutes": age_minutes,
        "fresh": age_minutes is not None and age_minutes <= 30,
        "temperatureF": c_to_f(temp_c),
        "dewpointF": c_to_f(dew_c),
        "humidityPercent": None if _value(p.get("relativeHumidity")) is None else round(_value(p.get("relativeHumidity")), 1),
        "windMph": ms_to_mph(_value(p.get("windSpeed"))),
        "windGustMph": ms_to_mph(_value(p.get("windGust"))),
        "windDirectionDegrees": _value(p.get("windDirection")),
        "visibilityMeters": _value(p.get("visibility")),
        "textDescription": p.get("textDescription"),
        "icon": p.get("icon"),
        "source": "National Weather Service observation",
    }


def current_conditions(engine, point: dict[str, Any]) -> dict[str, Any]:
    props = point.get("properties") or {}
    stations_url = props.get("observationStations")
    if not stations_url:
        return {"available": False, "reason": "NWS point response has no observationStations endpoint"}
    stations, stations_meta = engine._fetch_json(stations_url, f"stations:{stations_url}", 21600)
    features = stations.get("features") or []
    candidates = []
    for feature in features[:5]:
        station_url = (feature or {}).get("id")
        if not station_url: continue
        station_id = station_url.rstrip("/").split("/")[-1]
        try:
            obs, meta = engine._fetch_json(f"{station_url}/observations/latest", f"observation:{station_id}", 300)
            normalized = normalize_observation(obs, station_id)
            normalized["cache"] = meta
            if normalized.get("observedAt"): candidates.append(normalized)
        except Exception:
            continue
    candidates.sort(key=lambda item: item.get("ageMinutes") if item.get("ageMinutes") is not None else 999999)
    best = candidates[0] if candidates else None
    return {
        "available": best is not None,
        "best": best,
        "stationsChecked": min(5, len(features)),
        "alternates": candidates[1:3],
        "stationListCache": stations_meta,
        "source": "National Weather Service observation stations",
    }
