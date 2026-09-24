# MyUSA Google Cloud Admin MCP Connector

This connector is intentionally separate from the read-only MyUSA Analytics/Search connector.

## Scope

- Google Cloud project: `optimum-sound-505003-d3`
- Default display purpose: MyUSA.us Google measurement/search/performance infrastructure
- Only allowlisted Google APIs can be enabled.
- No credentials belong in GitHub.

## Tools

- `get_cloud_project` — show the locked project and API allowlist.
- `get_required_api_status` — read enabled/disabled status for the approved APIs.
- `enable_google_api(service, confirm)` — enable one approved API; requires `confirm=true`.
- `enable_myusa_core_apis(confirm)` — enable Analytics Data/Admin, Search Console, PageSpeed, and CrUX; requires `confirm=true`.

## Bootstrap requirement

Google's Service Usage API must be enabled before this connector can manage other APIs. For a newly-created project, complete this one bootstrap action while signed in as the project owner:

```bash
gcloud services enable serviceusage.googleapis.com --project=optimum-sound-505003-d3
```

Equivalent Cloud Console path: APIs & Services → Library → Service Usage API → Enable.

After that, run this connector using Google Application Default Credentials for a principal with `serviceusage.services.enable` permission. Google's predefined `Service Usage Admin` role (`roles/serviceusage.serviceUsageAdmin`) supplies the required API-management permission; use the narrowest practical IAM grant.

## Deployment

Designed for Cloud Run using the included Dockerfile. Set `MYUSA_GCP_PROJECT_ID` only if the project ID ever intentionally changes.

Do not make the Cloud Run endpoint public without authentication. Keep the admin connector separate from the public MyUSA.us website.
