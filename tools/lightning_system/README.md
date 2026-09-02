# MyUSA Live Lightning

Self-contained first implementation of a MyUSA lightning system built around NOAA GOES Geostationary Lightning Mapper (GLM) data.

## What this does

- Pulls recent GOES-East (GOES-19) and GOES-West (GOES-18) GLM Level-2 LCFA files from NOAA's public AWS buckets.
- Extracts flash latitude/longitude, first-event time, energy, and area.
- Emits a compact GeoJSON feed that can be cached and served by MyUSA.
- Provides a Leaflet-compatible browser overlay with 10, 20, and 30 mile range rings.
- Computes nearest observed GLM flash to the selected location and a flash count inside 30 miles.

## Important product wording

GLM is **total lightning observed from satellite**. It is not a precision ground-strike network. The UI should say `NOAA GOES satellite lightning` or `Lightning observed by NOAA GOES` and should not label individual points as exact ground strikes.

Recommended safety copy:

> Satellite lightning observations are informational and may not represent the exact ground-strike location. During dangerous weather, follow official NWS warnings and local emergency instructions.

## Backend

`glm_to_geojson.py` creates `latest-lightning.geojson` from the most recent LCFA files.

Example:

```bash
python -m pip install -r requirements.txt
python glm_to_geojson.py --minutes 30 --output latest-lightning.geojson
```

Run it every minute (or every 2 minutes initially) and publish/cache the resulting GeoJSON behind a MyUSA endpoint such as `/api/lightning`.

The script uses unsigned public S3 access; there are no NOAA API credentials to manage.

## Frontend

Load `myusa-lightning.js` after Leaflet, then attach the overlay to the existing radar map:

```js
const lightning = new MyUSALightning({
  map,
  feedUrl: '/api/lightning',
  center: { lat: 28.927, lon: -81.972 },
  refreshMs: 60000,
});

lightning.start();
```

Update the center whenever the user changes ZIP/city/GPS location:

```js
lightning.setCenter(lat, lon);
```

The instance dispatches a `myusa:lightning-update` browser event with:

- `nearestMiles`
- `nearestAgeMinutes`
- `within10`
- `within20`
- `within30`
- `count30`

This can drive a MyUSA alert badge such as `Lightning observed within 10 miles`.

## Recommended UI

Add a `Lightning` toggle to the existing radar layers. When enabled:

- show recent GLM flashes;
- display 10/20/30 mile rings around the selected location;
- show `Closest observed lightning: X mi · Y min ago`;
- use newest flashes more prominently than older ones;
- automatically refresh every 60 seconds;
- keep the radar animation independent so the user can turn either layer on/off.

## Production notes

1. Cache the generated GeoJSON at the edge for about 30-60 seconds.
2. Clip feed responses to the user's map bounding box before sending them to the browser if nationwide payload size becomes large.
3. Keep only the most recent 30 minutes in the public feed by default.
4. For nationwide coverage, combine GOES-19 and GOES-18 and deduplicate flashes in the overlap region if needed.
5. Treat the GLM feed as supplemental observational data, not an alerting replacement for official NWS warnings.
