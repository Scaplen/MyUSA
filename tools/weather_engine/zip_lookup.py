#!/usr/bin/env python3
"""ZIP-code location resolver for the MyUSA weather engine.

Uses a checked-in JSON map when present so production requests do not depend on a
third-party geocoder. The resolver normalizes ZIP input, validates coordinates,
and returns stable place metadata for the weather engine.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ZIP_RE = re.compile(r"^\d{5}$")
DEFAULT_DATA = Path(__file__).with_name("zip_centroids.json")


class ZipLookupError(ValueError):
    pass


def normalize_zip(value: str) -> str:
    value = str(value).strip()
    if not ZIP_RE.fullmatch(value):
        raise ZipLookupError("ZIP code must be exactly 5 digits")
    return value


def load_zip_map(path: Path = DEFAULT_DATA) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ZipLookupError("ZIP centroid data must be a JSON object")
    return payload


def resolve_zip(value: str, path: Path = DEFAULT_DATA) -> dict[str, Any]:
    zipcode = normalize_zip(value)
    record = load_zip_map(path).get(zipcode)
    if not record:
        raise ZipLookupError(f"ZIP code {zipcode} is not in the local centroid dataset")

    lat = float(record["lat"])
    lon = float(record["lon"])
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ZipLookupError(f"ZIP code {zipcode} has invalid coordinates")

    return {
        "zip": zipcode,
        "lat": lat,
        "lon": lon,
        "city": record.get("city"),
        "state": record.get("state"),
        "county": record.get("county"),
        "source": record.get("source", "MyUSA ZIP centroid dataset"),
    }
