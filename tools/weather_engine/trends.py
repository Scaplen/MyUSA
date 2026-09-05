#!/usr/bin/env python3
"""MyUSA local weather-trend scoring.

Trend signals are attention signals, not authoritative weather observations.
A trend may be elevated only when corroborated by the official weather bundle.
"""
from __future__ import annotations

from typing import Any

SEVERE_TERMS = {
    "tornado", "warning", "severe", "thunderstorm", "hail", "flood", "hurricane",
    "tropical", "lightning", "snow", "ice", "blizzard", "heat", "wind", "fog",
}


def _text(value: Any) -> str:
    return str(value or "").lower()


def official_context(weather: dict[str, Any]) -> set[str]:
    terms: set[str] = set()
    alerts = ((weather.get("alerts") or {}).get("features") or [])
    for alert in alerts:
        props = (alert or {}).get("properties") or {}
        for field in ("event", "headline", "description"):
            text = _text(props.get(field))
            terms.update(term for term in SEVERE_TERMS if term in text)

    periods = ((weather.get("forecast") or {}).get("properties") or {}).get("periods") or []
    for period in periods[:6]:
        text = " ".join((_text(period.get("shortForecast")), _text(period.get("detailedForecast"))))
        terms.update(term for term in SEVERE_TERMS if term in text)

    lightning = weather.get("lightning") or {}
    if lightning.get("available") and int(lightning.get("count") or 0) > 0:
        terms.add("lightning")
        terms.add("thunderstorm")
    return terms


def score_trends(weather: dict[str, Any], signals: list[dict[str, Any]]) -> dict[str, Any]:
    """Score normalized public attention signals against official local conditions.

    Expected signal shape: {topic, source, score, observedAt, url?}. Score is 0..100.
    The caller owns collection/licensing for each signal source.
    """
    confirmed = official_context(weather)
    ranked = []
    for signal in signals:
        topic = str(signal.get("topic") or "").strip()
        if not topic:
            continue
        raw_score = max(0.0, min(100.0, float(signal.get("score") or 0)))
        topic_text = topic.lower()
        matches = sorted(term for term in confirmed if term in topic_text or topic_text in term)
        corroborated = bool(matches)
        # Attention alone cannot create a weather event. Uncorroborated signals remain low priority.
        confidence = round((raw_score * (1.0 if corroborated else 0.25)), 1)
        ranked.append({
            "topic": topic,
            "source": signal.get("source"),
            "observedAt": signal.get("observedAt"),
            "url": signal.get("url"),
            "attentionScore": raw_score,
            "officiallyCorroborated": corroborated,
            "officialMatches": matches,
            "trendScore": confidence,
            "publishEligible": corroborated and confidence >= 35,
        })

    ranked.sort(key=lambda item: item["trendScore"], reverse=True)
    return {
        "sourceRole": "public attention signals; not authoritative weather data",
        "officialAuthority": "National Weather Service / NOAA",
        "items": ranked,
        "top": next((item for item in ranked if item["publishEligible"]), None),
    }
