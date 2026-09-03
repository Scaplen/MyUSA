#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import tempfile
from pathlib import Path

import boto3
import netCDF4
import numpy as np
from botocore import UNSIGNED
from botocore.config import Config

SATELLITES = {
    "G19": "noaa-goes19",
    "G18": "noaa-goes18",
}
PRODUCT = "GLM-L2-LCFA"


def utcnow():
    return dt.datetime.now(dt.timezone.utc)


def hour_prefix(t):
    return f"{PRODUCT}/{t.year}/{t.timetuple().tm_yday:03d}/{t.hour:02d}/"


def list_recent_keys(s3, bucket, minutes):
    cutoff = utcnow() - dt.timedelta(minutes=minutes + 3)
    hours = {cutoff.replace(minute=0, second=0, microsecond=0), utcnow().replace(minute=0, second=0, microsecond=0)}
    keys = []
    for h in sorted(hours):
        paginator = s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=hour_prefix(h)):
            for obj in page.get("Contents", []):
                if obj["LastModified"] >= cutoff and obj["Key"].endswith(".nc"):
                    keys.append(obj["Key"])
    return sorted(set(keys))


def as_float(v):
    try:
        if np.ma.is_masked(v):
            return None
        return float(v)
    except Exception:
        return None


def parse_file(path, satellite, cutoff):
    features = []
    with netCDF4.Dataset(path) as ds:
        lats = ds.variables.get("flash_lat")
        lons = ds.variables.get("flash_lon")
        if lats is None or lons is None:
            return features

        energy = ds.variables.get("flash_energy")
        area = ds.variables.get("flash_area")
        offsets = ds.variables.get("flash_time_offset_of_first_event")
        start_text = getattr(ds, "time_coverage_start", None)
        if not start_text:
            return features
        start = dt.datetime.fromisoformat(start_text.replace("Z", "+00:00"))

        for i in range(len(lats)):
            lat = as_float(lats[i])
            lon = as_float(lons[i])
            if lat is None or lon is None:
                continue
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                continue

            obs = start
            if offsets is not None:
                off = as_float(offsets[i])
                if off is not None:
                    obs = start + dt.timedelta(seconds=off)
            if obs < cutoff:
                continue

            props = {
                "satellite": satellite,
                "observed": obs.isoformat().replace("+00:00", "Z"),
                "energy": as_float(energy[i]) if energy is not None else None,
                "area": as_float(area[i]) if area is not None else None,
                "source": "NOAA GOES GLM",
            }
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": props,
            })
    return features


def collect(minutes):
    s3 = boto3.client("s3", config=Config(signature_version=UNSIGNED))
    cutoff = utcnow() - dt.timedelta(minutes=minutes)
    features = []
    satellites = {}

    with tempfile.TemporaryDirectory() as td:
        for sat, bucket in SATELLITES.items():
            keys = list_recent_keys(s3, bucket, minutes)
            satellite_features = []
            successful_files = 0
            for key in keys:
                local = os.path.join(td, f"{sat}-{os.path.basename(key)}")
                try:
                    s3.download_file(bucket, key, local)
                    satellite_features.extend(parse_file(local, sat, cutoff))
                    successful_files += 1
                except Exception as exc:
                    print(f"warning: failed {bucket}/{key}: {exc}")
            features.extend(satellite_features)
            newest = max(
                (feature["properties"]["observed"] for feature in satellite_features),
                default=None,
            )
            satellites[sat] = {
                "available": successful_files > 0,
                "objectCount": successful_files,
                "newestObservation": newest,
            }

    # Lightweight overlap dedupe: round location/time to avoid double-counting
    # very similar observations from East/West coverage overlap.
    unique = {}
    for f in features:
        lon, lat = f["geometry"]["coordinates"]
        when = f["properties"]["observed"][:19]
        key = (round(lat, 2), round(lon, 2), when)
        unique.setdefault(key, f)

    out = list(unique.values())
    out.sort(key=lambda f: f["properties"]["observed"])
    return out, satellites


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=int, default=30)
    ap.add_argument("--output", default="latest-lightning.geojson")
    args = ap.parse_args()

    features, satellites = collect(args.minutes)
    payload = {
        "type": "FeatureCollection",
        "generated": utcnow().isoformat().replace("+00:00", "Z"),
        "windowMinutes": args.minutes,
        "source": "NOAA GOES GLM Level-2 LCFA",
        "available": any(item["available"] for item in satellites.values()),
        "satellites": satellites,
        "features": features,
    }
    Path(args.output).write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {len(features)} flashes to {args.output}")


if __name__ == "__main__":
    main()
