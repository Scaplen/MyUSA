#!/usr/bin/env python3
import json, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path
from health import check_nws_health, classify_engine
from current_conditions import current_conditions
API_ROOT="https://api.weather.gov"; USER_AGENT="MyUSA.us weather engine (https://myusa.us)"
class WeatherEngine:
    def __init__(self,cache_dir=".cache/myusa-weather",timeout=12): self.cache_dir=Path(cache_dir); self.cache_dir.mkdir(parents=True,exist_ok=True); self.timeout=timeout
    def _cache_path(self,key): return self.cache_dir/f"{urllib.parse.quote(key,safe='')}.json"
    def _read_cache(self,key):
        path=self._cache_path(key)
        if not path.exists(): return None
        try: return json.loads(path.read_text(encoding="utf-8"))
        except Exception: return None
    def _write_cache(self,key,payload):
        wrapper={"savedAt":int(time.time()),"payload":payload}; self._cache_path(key).write_text(json.dumps(wrapper,separators=(",",":")),encoding="utf-8"); return wrapper
    def _fetch_json(self,url,cache_key,ttl_seconds):
        cached=self._read_cache(cache_key); now=int(time.time())
        if cached and now-cached.get("savedAt",0)<=ttl_seconds: return cached["payload"],{"cache":"fresh","stale":False}
        req=urllib.request.Request(url,headers={"User-Agent":USER_AGENT,"Accept":"application/geo+json, application/json"})
        try:
            with urllib.request.urlopen(req,timeout=self.timeout) as resp: payload=json.load(resp)
            self._write_cache(cache_key,payload); return payload,{"cache":"refreshed","stale":False}
        except (urllib.error.URLError,urllib.error.HTTPError,TimeoutError,json.JSONDecodeError) as exc:
            if cached:
                age=now-cached.get("savedAt",0); return cached["payload"],{"cache":"last-known-good","stale":True,"ageSeconds":age,"upstreamError":str(exc)}
            raise
    def point_metadata(self,lat,lon):
        lat=round(float(lat),4); lon=round(float(lon),4); return self._fetch_json(f"{API_ROOT}/points/{lat},{lon}",f"point:{lat},{lon}",86400)
    def forecast_bundle(self,lat,lon):
        point,point_meta=self.point_metadata(lat,lon); props=point.get("properties",{}); forecast_url=props.get("forecast"); hourly_url=props.get("forecastHourly")
        if not forecast_url or not hourly_url: raise RuntimeError("NWS point response did not include forecast endpoints")
        forecast,forecast_meta=self._fetch_json(forecast_url,f"forecast:{forecast_url}",900)
        hourly,hourly_meta=self._fetch_json(hourly_url,f"hourly:{hourly_url}",600)
        alerts,alerts_meta=self._fetch_json(f"{API_ROOT}/alerts/active?point={round(float(lat),4)},{round(float(lon),4)}",f"alerts:{round(float(lat),4)},{round(float(lon),4)}",60)
        observations=current_conditions(self,point)
        engine_meta={"source":"National Weather Service / api.weather.gov","point":point_meta,"forecast":forecast_meta,"hourly":hourly_meta,"alerts":alerts_meta,"usedFallback":any(m.get("stale") for m in (point_meta,forecast_meta,hourly_meta,alerts_meta))}
        engine_meta["health"]=classify_engine(engine_meta,check_nws_health(timeout=min(self.timeout,5)))
        return {"location":{"latitude":round(float(lat),4),"longitude":round(float(lon),4),"office":props.get("gridId"),"gridX":props.get("gridX"),"gridY":props.get("gridY"),"city":(props.get("relativeLocation") or {}).get("properties",{}).get("city"),"state":(props.get("relativeLocation") or {}).get("properties",{}).get("state")},"current":observations,"forecast":forecast,"hourly":hourly,"alerts":alerts,"engine":engine_meta}
if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser(); p.add_argument("lat",type=float); p.add_argument("lon",type=float); a=p.parse_args(); print(json.dumps(WeatherEngine().forecast_bundle(a.lat,a.lon),indent=2))
