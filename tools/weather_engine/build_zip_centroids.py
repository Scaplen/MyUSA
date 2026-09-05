#!/usr/bin/env python3
"""Build MyUSA's local ZIP/ZCTA centroid lookup from the U.S. Census Gazetteer.

The generated file is intentionally small and static. Runtime weather requests then
resolve ZIP -> coordinates locally, with no third-party geocoding call.
"""
from __future__ import annotations

import csv
import io
import json
import urllib.request
import zipfile
from pathlib import Path

SOURCE_URL = (
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
    "2025_Gazetteer/2025_Gaz_zcta_national.zip"
)
OUTPUT = Path(__file__).with_name("zip_centroids.json")
USER_AGENT = "MyUSA.us weather engine (https://myusa.us)"


def main() -> None:
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as response:
        archive_bytes = response.read()

    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        txt_names = [name for name in archive.namelist() if name.lower().endswith(".txt")]
        if not txt_names:
            raise RuntimeError("Census ZCTA archive did not contain a text file")
        raw = archive.read(txt_names[0]).decode("utf-8-sig")

    rows = csv.DictReader(io.StringIO(raw), delimiter="|")
    output: dict[str, dict[str, object]] = {}
    for row in rows:
        zipcode = (row.get("GEOID") or "").strip()
        lat_text = (row.get("INTPTLAT") or "").strip()
        lon_text = (row.get("INTPTLONG") or "").strip()
        if len(zipcode) != 5 or not zipcode.isdigit() or not lat_text or not lon_text:
            continue
        output[zipcode] = {
            "lat": float(lat_text),
            "lon": float(lon_text),
            "source": "U.S. Census Bureau 2025 ZCTA Gazetteer",
        }

    if len(output) < 30000:
        raise RuntimeError(f"unexpectedly small ZCTA dataset: {len(output)} records")

    OUTPUT.write_text(json.dumps(output, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    print(f"wrote {len(output)} ZCTA centroids to {OUTPUT}")


if __name__ == "__main__":
    main()
