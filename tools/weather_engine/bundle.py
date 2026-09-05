#!/usr/bin/env python3
"""Unified MyUSA weather-engine response by ZIP."""
from __future__ import annotations
import json, math, os, urllib.request
from typing import Any
from engine import WeatherEngine
from zip_lookup import resolve_zip
from trends import score_trends

DEFAULT_LIGHTNING_URL = os.environ.get("MYUSA_LIGHTNING_URL", "https://raw.githubusercontent.com/Scaplen/MyUSA/lightning-data/data/latest-lightning.geojson")
USER_AGENT = "MyUSA.us weather engine (https://myusa.us)"

def miles_between(lat1, lon1, lat2, lon2):
    r=3958.7613; p1=math.radians(lat1); p2=math.radians(lat2); dlat=math.radians(lat2-lat1); dlon=math.radians(lon2-lon1)
    a=math.sin(dlat/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dlon/2)**2
    return 2*r*math.asin(math.sqrt(a))

def nearby_lightning(lat: float, lon: float, radius_miles: float=30, timeout: int=8) -> dict[str,Any]:
    req=urllib.request.Request(DEFAULT_LIGHTNING_URL,headers={"User-Agent":USER_AGENT})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as response: payload=json.load(response)
        features=payload.get("features") if isinstance(payload,dict) else None
        if not isinstance(features,list): raise ValueError("lightning feed features missing")
        nearby=[]
        for feature in features:
            coords=((feature or {}).get("geometry") or {}).get("coordinates")
            if not isinstance(coords,list) or len(coords)<2: continue
            slon,slat=float(coords[0]),float(coords[1]); distance=miles_between(lat,lon,slat,slon)
            if distance<=radius_miles:
                props=dict((feature or {}).get("properties") or {}); props["distanceMiles"]=round(distance,1)
                nearby.append({"latitude":slat,"longitude":slon,**props})
        nearby.sort(key=lambda item:item["distanceMiles"])
        return {"available":bool(payload.get("available",True)),"source":payload.get("source","NOAA GOES GLM via MyUSA"),"generated":payload.get("generated"),"radiusMiles":radius_miles,"count":len(nearby),"closestMiles":nearby[0]["distanceMiles"] if nearby else None,"flashes":nearby}
    except Exception as exc:
        return {"available":False,"source":"NOAA GOES GLM via MyUSA","radiusMiles":radius_miles,"count":0,"closestMiles":None,"flashes":[],"error":str(exc)}

def bundle_for_zip(zipcode: str, include_lightning: bool=True, trend_signals: list[dict[str,Any]]|None=None) -> dict[str,Any]:
    resolved=resolve_zip(zipcode)
    weather=WeatherEngine().forecast_bundle(resolved["lat"],resolved["lon"])
    weather["requestedLocation"]=resolved
    weather["engine"]["zipResolution"]={"source":resolved["source"],"localLookup":True}
    if include_lightning: weather["lightning"]=nearby_lightning(resolved["lat"],resolved["lon"])
    weather["trends"]=score_trends(weather,trend_signals or [])
    return weather

if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser(); parser.add_argument("zip"); parser.add_argument("--no-lightning",action="store_true")
    args=parser.parse_args(); print(json.dumps(bundle_for_zip(args.zip,not args.no_lightning),indent=2))
