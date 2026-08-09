# MyUSA.us YouTube Publishing Connector

Target channel: `https://www.youtube.com/@MyUSAus`

A separate, write-capable MCP service for the MyUSA.us YouTube channel.

## Safety defaults

- The intended publishing destination is the `@MyUSAus` YouTube channel only.
- Cloud Run stays private and IAM-protected.
- OAuth credentials and the refresh token belong only in Google Secret Manager, never in GitHub.
- YouTube service accounts are not used; ordinary YouTube channel publishing requires OAuth 2.0 authorization by the channel owner.
- Uploads default to private.
- Public publishing is rejected unless `MYUSA_YOUTUBE_ALLOW_PUBLIC=true` is deliberately enabled on the server.
- After the first successful OAuth verification, the exact internal channel ID returned for `@MyUSAus` must be saved as `MYUSA_YOUTUBE_CHANNEL_ID`; the connector then blocks publishing if OAuth ever resolves to another channel.
- Videos are read only from the configured private Cloud Storage staging bucket.
- The staging bucket uses an automatic short retention lifecycle to limit storage buildup.
- Cloud Run uses minimum instances 0 and maximum instances 1.

## MCP tools

- `authorization_status` verifies OAuth and channel binding without changing YouTube.
- `get_channel_summary` reads channel identity and aggregate stats.
- `list_recent_videos` reads recent channel uploads.
- `upload_video_from_gcs` performs a resumable upload from the MyUSA staging bucket and defaults to private.
- `set_video_privacy` changes privacy; public is server-gated.
- `update_video_metadata` updates title, description, tags, and category.

## One-time Cloud setup

Run `setup_youtube_cloud.sh` from the repository root on branch `feature/youtube-publisher`.

The script enables the required APIs, creates a dedicated `myusa-youtube-publisher` runtime service account, creates a private staging bucket, adds a short object lifecycle policy, and creates empty Secret Manager entries for the OAuth client ID, client secret, and refresh token.

## One-time YouTube authorization

In Google Cloud Console for project `optimum-sound-505003-d3`, configure the OAuth consent screen and create an OAuth client for the publishing workflow. Authorize the Google account that owns or manages `https://www.youtube.com/@MyUSAus` with YouTube upload and YouTube management scopes and request offline access so a refresh token is issued.

Add the OAuth client ID, client secret, and refresh token directly to their matching Secret Manager entries using Google Cloud Console or Cloud Shell. Never put those values in repository files, issues, pull requests, workflow variables, or chat messages.

## Deploy

After all three Secret Manager entries have a current version, manually run the GitHub Actions workflow `Deploy MyUSA YouTube Publisher`.

Deployment target:

- Service: `myusa-youtube-publisher`
- Region: `us-east1`
- Runtime identity: `myusa-youtube-publisher@optimum-sound-505003-d3.iam.gserviceaccount.com`
- Min instances: 0
- Max instances: 1
- MCP path: `/mcp`

The workflow reuses the existing keyless GitHub to Google Cloud Workload Identity Federation trust.

## First verification

Call `authorization_status` and `get_channel_summary`. Confirm the authorized channel custom URL/handle is `@MyUSAus`. Record the returned internal channel ID and set `MYUSA_YOUTUBE_CHANNEL_ID` on Cloud Run to that exact value before allowing any publishing beyond private test uploads.

Keep public publishing disabled while testing. Google documents that uploads from qualifying unverified API projects are restricted to private viewing until the project completes the required API compliance audit.
