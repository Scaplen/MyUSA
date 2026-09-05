# MyUSA Weather Engine Core

This module provides a resilient server-side wrapper around the National Weather Service API for MyUSA.us.

## Goals

- One normalized backend call for point metadata, 7-day forecast, hourly forecast, and active alerts.
- Reduce repeated browser-to-NWS calls.
- Cache NWS point-to-grid mappings for 24 hours.
- Cache forecasts for 15 minutes and hourly data for 10 minutes.
- Cache active alerts briefly (60 seconds).
- Preserve and serve last-known-good data when api.weather.gov is temporarily unavailable.
- Mark fallback responses clearly in `engine.usedFallback` and per-source metadata so the UI can display data age instead of silently pretending stale data is live.

## Example

```bash
python tools/weather_engine/engine.py 28.9270 -81.9753
```

## Integration target

The live MyUSA backend should call `WeatherEngine().forecast_bundle(lat, lon)` (or port this logic into its server runtime), then expose the resulting normalized object to the front end. ZIP-to-coordinate resolution should happen before this call and should itself be cached.

## Important behavior

A stale forecast is safer than a false blank forecast during a short NOAA/NWS outage, but the user interface must disclose when fallback data is being used and how old it is. Alerts should use a much shorter cache window than forecasts.

Official source: National Weather Service API (`api.weather.gov`).
