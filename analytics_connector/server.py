import os
from datetime import date, timedelta
from typing import Any
from urllib.parse import urlparse

import google.auth
import requests
from google.analytics.admin_v1beta import AnalyticsAdminServiceClient
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Filter,
    FilterExpression,
    Metric,
    RunRealtimeReportRequest,
    RunReportRequest,
)
from googleapiclient.discovery import build
from mcp.server.fastmcp import FastMCP

PROPERTY_ID = os.getenv("MYUSA_GA4_PROPERTY_ID", "527458725")
PROPERTY = f"properties/{PROPERTY_ID}"
SEARCH_CONSOLE_SITE = os.getenv("MYUSA_SEARCH_CONSOLE_SITE", "https://myusa.us/")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
PORT = int(os.getenv("PORT", "8080"))
MYUSA_HOSTS = {"myusa.us", "www.myusa.us"}
GOOGLE_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

mcp = FastMCP("MyUSA Google Growth Stack")
data_client = BetaAnalyticsDataClient()
admin_client = AnalyticsAdminServiceClient()
credentials, _ = google.auth.default(scopes=GOOGLE_SCOPES)
search_console = build("searchconsole", "v1", credentials=credentials, cache_discovery=False)


def _rows(response: Any) -> list[dict[str, Any]]:
    dimensions = [h.name for h in response.dimension_headers]
    metrics = [h.name for h in response.metric_headers]
    rows: list[dict[str, Any]] = []
    for row in response.rows:
        item: dict[str, Any] = {}
        for name, value in zip(dimensions, row.dimension_values):
            item[name] = value.value
        for name, value in zip(metrics, row.metric_values):
            item[name] = value.value
        rows.append(item)
    return rows


def _require_myusa_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or (parsed.hostname or "").lower() not in MYUSA_HOSTS:
        raise ValueError("Only myusa.us and www.myusa.us URLs are allowed.")
    return url


def _myusa_stream_id() -> str:
    """Resolve the GA4 web stream whose configured default URI is MyUSA.us."""
    for stream in admin_client.list_data_streams(parent=PROPERTY):
        details = getattr(stream, "web_stream_data", None)
        default_uri = getattr(details, "default_uri", "") if details else ""
        host = urlparse(default_uri).hostname or ""
        if host.lower() in MYUSA_HOSTS:
            return stream.name.rsplit("/", 1)[-1]
    raise RuntimeError(
        "No GA4 web data stream for myusa.us/www.myusa.us was found in "
        f"property {PROPERTY_ID}. Refusing to return mixed-site analytics."
    )


def _myusa_filter() -> FilterExpression:
    return FilterExpression(
        filter=Filter(
            field_name="streamId",
            in_list_filter=Filter.InListFilter(values=[_myusa_stream_id()]),
        )
    )


def _date_window(days: int) -> tuple[str, str]:
    days = max(1, min(days, 486))
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=days - 1)
    return start.isoformat(), end.isoformat()


def _search_analytics(dimensions: list[str], days: int, limit: int) -> dict[str, Any]:
    start_date, end_date = _date_window(days)
    body = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": dimensions,
        "rowLimit": max(1, min(limit, 25000)),
        "dataState": "all",
    }
    return search_console.searchanalytics().query(siteUrl=SEARCH_CONSOLE_SITE, body=body).execute()


@mcp.tool()
def get_property_details() -> dict[str, Any]:
    """Return MyUSA.us GA4 property and stream details only."""
    prop = admin_client.get_property(name=PROPERTY)
    return {
        "site": "MyUSA.us",
        "property_id": PROPERTY_ID,
        "stream_id": _myusa_stream_id(),
        "display_name": prop.display_name,
        "time_zone": prop.time_zone,
        "currency_code": prop.currency_code,
        "search_console_site": SEARCH_CONSOLE_SITE,
    }


@mcp.tool()
def get_realtime_summary() -> list[dict[str, Any]]:
    """Return current MyUSA.us active users only, excluding every other site."""
    response = data_client.run_realtime_report(
        RunRealtimeReportRequest(
            property=PROPERTY,
            dimension_filter=_myusa_filter(),
            dimensions=[Dimension(name="country"), Dimension(name="deviceCategory")],
            metrics=[Metric(name="activeUsers"), Metric(name="screenPageViews")],
            limit=100,
        )
    )
    return _rows(response)


@mcp.tool()
def get_traffic_overview(days: int = 7) -> list[dict[str, Any]]:
    """Return MyUSA.us daily users, sessions, views, and engagement for the last N days."""
    days = max(1, min(days, 90))
    response = data_client.run_report(
        RunReportRequest(
            property=PROPERTY,
            dimension_filter=_myusa_filter(),
            date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
            dimensions=[Dimension(name="date")],
            metrics=[
                Metric(name="activeUsers"),
                Metric(name="sessions"),
                Metric(name="screenPageViews"),
                Metric(name="engagedSessions"),
            ],
            limit=100,
        )
    )
    return _rows(response)


@mcp.tool()
def get_top_pages(days: int = 7, limit: int = 25) -> list[dict[str, Any]]:
    """Return the most-viewed MyUSA.us pages only."""
    days = max(1, min(days, 90))
    response = data_client.run_report(
        RunReportRequest(
            property=PROPERTY,
            dimension_filter=_myusa_filter(),
            date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
            dimensions=[Dimension(name="pagePath")],
            metrics=[Metric(name="screenPageViews"), Metric(name="activeUsers")],
            limit=max(1, min(limit, 100)),
        )
    )
    return _rows(response)


@mcp.tool()
def get_top_sources(days: int = 7, limit: int = 25) -> list[dict[str, Any]]:
    """Return traffic sources for MyUSA.us only."""
    days = max(1, min(days, 90))
    response = data_client.run_report(
        RunReportRequest(
            property=PROPERTY,
            dimension_filter=_myusa_filter(),
            date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
            dimensions=[Dimension(name="sessionSource"), Dimension(name="sessionMedium")],
            metrics=[Metric(name="sessions"), Metric(name="activeUsers")],
            limit=max(1, min(limit, 100)),
        )
    )
    return _rows(response)


@mcp.tool()
def get_events(days: int = 7, limit: int = 50) -> list[dict[str, Any]]:
    """Return MyUSA.us events only, including ZIP searches and trend-card activity."""
    days = max(1, min(days, 90))
    response = data_client.run_report(
        RunReportRequest(
            property=PROPERTY,
            dimension_filter=_myusa_filter(),
            date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
            dimensions=[Dimension(name="eventName")],
            metrics=[Metric(name="eventCount"), Metric(name="activeUsers")],
            limit=max(1, min(limit, 100)),
        )
    )
    return _rows(response)


@mcp.tool()
def get_google_search_summary(days: int = 7) -> dict[str, Any]:
    """Return MyUSA.us Google Search clicks, impressions, CTR, and average position."""
    data = _search_analytics([], days, 1)
    rows = data.get("rows", [])
    row = rows[0] if rows else {}
    return {
        "days": days,
        "clicks": row.get("clicks", 0),
        "impressions": row.get("impressions", 0),
        "ctr": row.get("ctr", 0),
        "position": row.get("position", 0),
    }


@mcp.tool()
def get_google_search_queries(days: int = 7, limit: int = 50) -> list[dict[str, Any]]:
    """Return the Google queries finding MyUSA.us, with clicks, impressions, CTR, and position."""
    data = _search_analytics(["query"], days, limit)
    return [
        {
            "query": r.get("keys", [""])[0],
            "clicks": r.get("clicks", 0),
            "impressions": r.get("impressions", 0),
            "ctr": r.get("ctr", 0),
            "position": r.get("position", 0),
        }
        for r in data.get("rows", [])
    ]


@mcp.tool()
def get_google_search_pages(days: int = 7, limit: int = 50) -> list[dict[str, Any]]:
    """Return MyUSA.us pages appearing in Google Search and their performance."""
    data = _search_analytics(["page"], days, limit)
    return [
        {
            "page": r.get("keys", [""])[0],
            "clicks": r.get("clicks", 0),
            "impressions": r.get("impressions", 0),
            "ctr": r.get("ctr", 0),
            "position": r.get("position", 0),
        }
        for r in data.get("rows", [])
    ]


@mcp.tool()
def get_sitemaps() -> list[dict[str, Any]]:
    """List sitemaps Google Search Console knows for MyUSA.us."""
    data = search_console.sitemaps().list(siteUrl=SEARCH_CONSOLE_SITE).execute()
    return data.get("sitemap", [])


@mcp.tool()
def inspect_google_index(url: str) -> dict[str, Any]:
    """Inspect Google's indexed version/status of a MyUSA.us URL."""
    url = _require_myusa_url(url)
    body = {"inspectionUrl": url, "siteUrl": SEARCH_CONSOLE_SITE, "languageCode": "en-US"}
    return search_console.urlInspection().index().inspect(body=body).execute()


@mcp.tool()
def get_pagespeed(url: str = "https://myusa.us/", strategy: str = "mobile") -> dict[str, Any]:
    """Run Google's PageSpeed/Lighthouse analysis for a MyUSA.us page."""
    url = _require_myusa_url(url)
    strategy = strategy.lower()
    if strategy not in {"mobile", "desktop"}:
        raise ValueError("strategy must be mobile or desktop")
    params = {
        "url": url,
        "strategy": strategy,
        "category": ["performance", "accessibility", "best-practices", "seo"],
    }
    if GOOGLE_API_KEY:
        params["key"] = GOOGLE_API_KEY
    response = requests.get(
        "https://pagespeedonline.googleapis.com/pagespeedonline/v5/runPagespeed",
        params=params,
        timeout=90,
    )
    response.raise_for_status()
    data = response.json()
    lighthouse = data.get("lighthouseResult", {})
    categories = lighthouse.get("categories", {})
    audits = lighthouse.get("audits", {})
    return {
        "url": url,
        "strategy": strategy,
        "scores": {name: round((value.get("score") or 0) * 100) for name, value in categories.items()},
        "metrics": {
            key: audits.get(key, {}).get("displayValue")
            for key in [
                "largest-contentful-paint",
                "interaction-to-next-paint",
                "cumulative-layout-shift",
                "speed-index",
                "total-blocking-time",
            ]
        },
    }


@mcp.tool()
def get_crux(url: str = "https://myusa.us/") -> dict[str, Any]:
    """Return Google's CrUX real-user Core Web Vitals for a MyUSA.us page."""
    url = _require_myusa_url(url)
    if not GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY is required for the CrUX API.")
    response = requests.post(
        f"https://chromeuxreport.googleapis.com/v1/records:queryRecord?key={GOOGLE_API_KEY}",
        json={"url": url},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=PORT,
        streamable_http_path="/mcp",
    )
