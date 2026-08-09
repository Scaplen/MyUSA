import os
from typing import Any
from urllib.parse import urlparse

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
from google.analytics.admin_v1beta import AnalyticsAdminServiceClient
from mcp.server.fastmcp import FastMCP

PROPERTY_ID = os.getenv("MYUSA_GA4_PROPERTY_ID", "527458725")
PROPERTY = f"properties/{PROPERTY_ID}"
PORT = int(os.getenv("PORT", "8080"))
MYUSA_HOSTS = {"myusa.us", "www.myusa.us"}

mcp = FastMCP("MyUSA Google Analytics")
data_client = BetaAnalyticsDataClient()
admin_client = AnalyticsAdminServiceClient()


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
    stream_id = _myusa_stream_id()
    return FilterExpression(
        filter=Filter(
            field_name="streamId",
            in_list_filter=Filter.InListFilter(values=[stream_id]),
        )
    )


@mcp.tool()
def get_property_details() -> dict[str, Any]:
    """Return MyUSA.us GA4 property and stream details only."""
    prop = admin_client.get_property(name=PROPERTY)
    stream_id = _myusa_stream_id()
    return {
        "site": "MyUSA.us",
        "property_id": PROPERTY_ID,
        "stream_id": stream_id,
        "display_name": prop.display_name,
        "time_zone": prop.time_zone,
        "currency_code": prop.currency_code,
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
    limit = max(1, min(limit, 100))
    response = data_client.run_report(
        RunReportRequest(
            property=PROPERTY,
            dimension_filter=_myusa_filter(),
            date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
            dimensions=[Dimension(name="pagePath")],
            metrics=[Metric(name="screenPageViews"), Metric(name="activeUsers")],
            limit=limit,
        )
    )
    return _rows(response)


@mcp.tool()
def get_top_sources(days: int = 7, limit: int = 25) -> list[dict[str, Any]]:
    """Return traffic sources for MyUSA.us only."""
    days = max(1, min(days, 90))
    limit = max(1, min(limit, 100))
    response = data_client.run_report(
        RunReportRequest(
            property=PROPERTY,
            dimension_filter=_myusa_filter(),
            date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
            dimensions=[Dimension(name="sessionSource"), Dimension(name="sessionMedium")],
            metrics=[Metric(name="sessions"), Metric(name="activeUsers")],
            limit=limit,
        )
    )
    return _rows(response)


@mcp.tool()
def get_events(days: int = 7, limit: int = 50) -> list[dict[str, Any]]:
    """Return MyUSA.us events only, including ZIP searches and trend-card activity."""
    days = max(1, min(days, 90))
    limit = max(1, min(limit, 100))
    response = data_client.run_report(
        RunReportRequest(
            property=PROPERTY,
            dimension_filter=_myusa_filter(),
            date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
            dimensions=[Dimension(name="eventName")],
            metrics=[Metric(name="eventCount"), Metric(name="activeUsers")],
            limit=limit,
        )
    )
    return _rows(response)


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=PORT,
        streamable_http_path="/mcp",
    )
