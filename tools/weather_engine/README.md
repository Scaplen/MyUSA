# MyUSA Weather Engine Core

This module provides a resilient server-side wrapper around the National Weather Service API for MyUSA.us.

## Goals

- One normalized backend call for point metadata, 7-day forecast, hourly forecast, active alerts, current observations, and optional MyUSA lightning data.
- Reduce repeated browser-to-NWS calls.
- Cache NWS point-to-grid mappings for 24 hours.
- Cache forecasts for 15 minutes and hourly data for 10 minutes.
- Cache active alerts briefly (60 seconds).
- Retry short-lived upstream failures with jittered exponential backoff.
- Preserve and serve last-known-good data during short upstream outages, with hard age limits by data type.
- Use atomic cache writes so interrupted processes do not leave partially written cache files.
- Check nearby observation stations concurrently to reduce current-condition latency.
- Reuse the engine cache/fallback layer for the MyUSA lightning feed.
- Mark fallback responses clearly in `engine.usedFallback` and per-source metadata so the UI can display data age instead of silently pretending stale data is live.
- Expose upstream attempts/latency and total engine request duration for operations monitoring.

## Freshness guardrails

Current defaults are intentionally stricter for time-sensitive data:

- Point metadata fallback: up to 7 days.
- Forecast fallback: up to 6 hours.
- Hourly fallback: up to 3 hours.
- Alert fallback: up to 15 minutes.
- Observation fallback: up to 90 minutes.
- Lightning fallback: up to 5 minutes.

If cached data is older than the applicable maximum, the engine fails that source instead of presenting dangerously old information as current.

## Example

```bash
python tools/weather_engine/engine.py 28.9270 -81.9753
python tools/weather_engine/bundle.py 32162
```

## Integration target

The live MyUSA backend should call `WeatherEngine().forecast_bundle(lat, lon)` or `bundle_for_zip(zip)` (or port this logic into its server runtime), then expose the normalized object to the front end. ZIP-to-coordinate resolution happens before the weather call and is local/cached.

## Important behavior

A stale forecast can be preferable to a blank forecast during a short NOAA/NWS outage, but the user interface must disclose when fallback data is being used and how old it is. Alerts, current observations, and lightning use much shorter fallback limits than general forecasts.

Official primary source: National Weather Service API (`api.weather.gov`). Lightning source: NOAA GOES GLM via the MyUSA lightning feed.
