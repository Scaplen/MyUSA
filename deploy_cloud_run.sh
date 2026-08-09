#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="optimum-sound-505003-d3"
REGION="us-east1"
SERVICE="myusa-google-connector"
SERVICE_ACCOUNT="myusa-google-connector@optimum-sound-505003-d3.iam.gserviceaccount.com"
BRANCH="feature/ga4-mcp-connector"
REPO_URL="https://github.com/Scaplen/MyUSA.git"

# Required APIs for source deployment and runtime.
gcloud config set project "$PROJECT_ID"
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  analyticsdata.googleapis.com \
  analyticsadmin.googleapis.com \
  searchconsole.googleapis.com \
  pagespeedonline.googleapis.com \
  chromeuxreport.googleapis.com \
  serviceusage.googleapis.com

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$WORKDIR/MyUSA"
cd "$WORKDIR/MyUSA"

gcloud run deploy "$SERVICE" \
  --source analytics_connector \
  --region "$REGION" \
  --service-account "$SERVICE_ACCOUNT" \
  --no-allow-unauthenticated \
  --ingress all \
  --cpu 1 \
  --memory 512Mi \
  --min 0 \
  --max 1 \
  --port 8080 \
  --set-env-vars "MYUSA_GA4_PROPERTY_ID=527458725,MYUSA_SEARCH_CONSOLE_SITE=https://myusa.us/" \
  --quiet

URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')"
echo ""
echo "Deployment complete."
echo "Cloud Run service: $SERVICE"
echo "URL: $URL"
echo "MCP endpoint: $URL/mcp"
