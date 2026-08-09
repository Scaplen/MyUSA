import os
from typing import Any

import google.auth
from google.auth.transport.requests import AuthorizedSession
from mcp.server.fastmcp import FastMCP

PROJECT_ID = os.getenv("MYUSA_GCP_PROJECT_ID", "optimum-sound-505003-d3")
PORT = int(os.getenv("PORT", "8080"))

# Deliberately restricted to services needed for the MyUSA Google growth stack.
ALLOWED_SERVICES = {
    "serviceusage.googleapis.com": "Service Usage API",
    "analyticsdata.googleapis.com": "Google Analytics Data API",
    "analyticsadmin.googleapis.com": "Google Analytics Admin API",
    "searchconsole.googleapis.com": "Google Search Console API",
    "pagespeedonline.googleapis.com": "PageSpeed Insights API",
    "chromeuxreport.googleapis.com": "Chrome UX Report API",
    "cloudresourcemanager.googleapis.com": "Cloud Resource Manager API",
    "iam.googleapis.com": "Identity and Access Management API",
    "run.googleapis.com": "Cloud Run Admin API",
    "secretmanager.googleapis.com": "Secret Manager API",
    "artifactregistry.googleapis.com": "Artifact Registry API",
    "cloudbuild.googleapis.com": "Cloud Build API",
}

SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
credentials, _ = google.auth.default(scopes=SCOPES)
session = AuthorizedSession(credentials)

mcp = FastMCP("MyUSA Google Cloud Admin")


def _service_url(service: str) -> str:
    return f"https://serviceusage.googleapis.com/v1/projects/{PROJECT_ID}/services/{service}"


def _require_allowed(service: str) -> str:
    service = service.strip().lower()
    if service not in ALLOWED_SERVICES:
        raise ValueError(
            "Service is not in the MyUSA allowlist. Allowed services: "
            + ", ".join(sorted(ALLOWED_SERVICES))
        )
    return service


def _service_state(service: str) -> dict[str, Any]:
    response = session.get(_service_url(service), timeout=30)
    response.raise_for_status()
    data = response.json()
    return {
        "service": service,
        "title": ALLOWED_SERVICES[service],
        "state": data.get("state", "STATE_UNSPECIFIED"),
    }


@mcp.tool()
def get_cloud_project() -> dict[str, Any]:
    """Return the Google Cloud project this connector is permanently scoped to."""
    return {
        "project_id": PROJECT_ID,
        "purpose": "MyUSA.us Google analytics, search, performance, and connector infrastructure",
        "allowed_services": ALLOWED_SERVICES,
    }


@mcp.tool()
def get_required_api_status() -> list[dict[str, Any]]:
    """Check enabled/disabled status for every Google API approved for MyUSA."""
    results: list[dict[str, Any]] = []
    for service in ALLOWED_SERVICES:
        try:
            results.append(_service_state(service))
        except Exception as exc:
            results.append(
                {
                    "service": service,
                    "title": ALLOWED_SERVICES[service],
                    "state": "ERROR",
                    "error": type(exc).__name__,
                    "message": str(exc),
                }
            )
    return results


@mcp.tool()
def enable_google_api(service: str, confirm: bool = False) -> dict[str, Any]:
    """Enable one allowlisted Google API for MyUSA. Requires confirm=true."""
    service = _require_allowed(service)
    if not confirm:
        return {
            "changed": False,
            "project_id": PROJECT_ID,
            "service": service,
            "title": ALLOWED_SERVICES[service],
            "message": "No change made. Call again with confirm=true to enable this service.",
        }

    current = _service_state(service)
    if current["state"] == "ENABLED":
        return {"changed": False, "project_id": PROJECT_ID, **current}

    response = session.post(f"{_service_url(service)}:enable", json={}, timeout=30)
    response.raise_for_status()
    operation = response.json()
    return {
        "changed": True,
        "project_id": PROJECT_ID,
        "service": service,
        "title": ALLOWED_SERVICES[service],
        "operation": operation.get("name"),
        "message": "Enable request accepted. Use get_required_api_status to verify completion.",
    }


@mcp.tool()
def enable_myusa_core_apis(confirm: bool = False) -> dict[str, Any]:
    """Enable only the core MyUSA measurement/search APIs. Requires confirm=true."""
    core = [
        "analyticsdata.googleapis.com",
        "analyticsadmin.googleapis.com",
        "searchconsole.googleapis.com",
        "pagespeedonline.googleapis.com",
        "chromeuxreport.googleapis.com",
    ]
    if not confirm:
        return {
            "changed": False,
            "project_id": PROJECT_ID,
            "services": core,
            "message": "No change made. Call again with confirm=true to enable the core MyUSA APIs.",
        }

    results = []
    for service in core:
        try:
            current = _service_state(service)
            if current["state"] == "ENABLED":
                results.append({"service": service, "changed": False, "state": "ENABLED"})
                continue
            response = session.post(f"{_service_url(service)}:enable", json={}, timeout=30)
            response.raise_for_status()
            results.append(
                {
                    "service": service,
                    "changed": True,
                    "operation": response.json().get("name"),
                }
            )
        except Exception as exc:
            results.append(
                {
                    "service": service,
                    "changed": False,
                    "state": "ERROR",
                    "error": type(exc).__name__,
                    "message": str(exc),
                }
            )
    return {"project_id": PROJECT_ID, "results": results}


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=PORT,
        streamable_http_path="/mcp",
    )
