import os
from typing import Any

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunRealtimeReportRequest, RunReportRequest
from google.analytics.admin_v1beta import AnalyticsAdminServiceClient
from mcp.server.fastmcp import FastMCP

PROPERTY_ID = os.getenv("MYUSA_GA4_PROPERTY_ID", "527458725")
PROPERTY = f"properties/{PROPERTY_ID}"

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


@mcp.tool()
def get_property_details() -> dict[str, Any]:
    """Return basic details for the MyUSA.us GA4 property."""
    prop = admin_client.get_property(name=PROPERTY)
    return {
        "property_id": PROPERTY_ID,
        "display_name": prop.display_name,
        "time_zone": prop.time_zone,
        "currency_code": prop.currency_code,
        "industry_category": str(prop.industry_category),
        "service_level": str(prop.service_level),
    }


@mcp.tool()
def get_realtime_summary() -> list[dict[str, Any]]:
    """Return current MyUSA.us active users grouped by country and device category."""
    response = data_client.run_realtime_report(
        RunRealtimeReportRequest(
            property=PROPERTY,
            dimensions=[Dimension(name="country"), Dimension(name="deviceCategory")],
            metrics=[Metric(name="activeUsers")],
            limit=100,
        )
    )
    return _rows(response)


@mcp.tool()
def get_traffic_overview(days: int = 7) -> list[dict[str, Any]]:
    """Return daily users, sessions, page views, and engagement for the last N days."""
    days = max(1, min(days, 90))
    response = data_client.run_report(
        RunReportRequest(
            property=PROPERTY,
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
    """Return the most-viewed MyUSA.us pages for the selected period."""
    days = max(1, min(days, 90))
    limit = max(1, min(limit, 100))
    response = data_client.run_report(
        RunReportRequest(
            property=PROPERTY,
            date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
            dimensions=[Dimension(name="pagePath")],
            metrics=[Metric(name="screenPageViews"), Metric(name="activeUsers")],
            limit=limit,
        )
    )
    return _rows(response)


@mcp.tool()
def get_top_sources(days: int = 7, limit: int = 25) -> list[dict[str, Any]]:
    """Return MyUSA.us traffic sources and session counts."""
    days = max(1, min(days, 90))
    limit = max(1, min(limit, 100))
    response = data_client.run_report(
        RunReportRequest(
            property=PROPERTY,
            date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
            dimensions=[Dimension(name="sessionSource"), Dimension(name="sessionMedium")],
            metrics=[Metric(name="sessions"), Metric(name="activeUsers")],
            limit=limit,
        )
    )
    return _rows(response)


@mcp.tool()
def get_events(days: int = 7, limit: int = 50) -> list[dict[str, Any]]:
    """Return event names and counts, useful for ZIP searches and trend-card tracking."""
    days = max(1, min(days, 90))
    limit = max(1, min(limit, 100))
    response = data_client.run_report(
        RunReportRequest(
            property=PROPERTY,
            date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
            dimensions=[Dimension(name="eventName")],
            metrics=[Metric(name="eventCount"), Metric(name="activeUsers")],
            limit=limit,
        )
    )
    return _rows(response)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
