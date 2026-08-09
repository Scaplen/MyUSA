# MyUSA.us Google Analytics MCP connector

This connector gives ChatGPT read-only access to the MyUSA.us Google Analytics 4 property.

- GA4 property ID: `527458725`
- MCP endpoint after deployment: `/mcp`
- Intended permissions: Analytics Viewer/read-only only
- Credentials are supplied by Google Cloud at runtime and are never committed to GitHub.
- Deployment is automated through GitHub Actions using Google Workload Identity Federation; no service-account key is stored in GitHub.

## What it exposes

- `get_property_details`
- `get_realtime_summary`
- `get_traffic_overview`
- `get_top_pages`
- `get_top_sources`
- `get_events`

The server is hard-locked to the MyUSA.us property ID by default.

## Google setup

1. In Google Cloud, enable the Google Analytics Data API and Google Analytics Admin API.
2. Create or choose a service account for this connector.
3. In GA4 property 527458725, open Admin > Property access management and add the service-account email with Viewer permission only.
4. Deploy this folder to Cloud Run using that service account as the runtime identity.

Example deployment from the repository root:

```bash
gcloud run deploy myusa-ga4-mcp \
  --source . \
  --region us-east1 \
  --service-account YOUR_SERVICE_ACCOUNT_EMAIL \
  --set-env-vars MYUSA_GA4_PROPERTY_ID=527458725
```

Use `analytics_connector/Dockerfile` as the container definition in your build configuration.

## ChatGPT connection

ChatGPT custom MCP apps require a remote MCP endpoint. After Cloud Run deployment, use:

```text
https://YOUR_CLOUD_RUN_HOST/mcp
```

For ChatGPT Pro, enable Developer mode and create a custom app with read/fetch permissions. Do not expose the endpoint publicly without an authentication layer appropriate for your deployment.

## Security rules

- Never commit a service-account JSON key.
- Prefer a Cloud Run runtime service account / Application Default Credentials.
- Grant GA4 Viewer only, not Editor or Administrator.
- Keep the connector property-scoped to `527458725`.
- Add remote endpoint authentication before connecting production Analytics data to ChatGPT.
