#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="optimum-sound-505003-d3"
PROJECT_NUMBER="265519813462"
REGION="us-east1"
DEPLOYER_SA="myusa-github-deployer@${PROJECT_ID}.iam.gserviceaccount.com"
YOUTUBE_SA="myusa-youtube-publisher@${PROJECT_ID}.iam.gserviceaccount.com"
BUCKET="myusa-youtube-staging-${PROJECT_NUMBER}"

SECRETS=(
  myusa-youtube-client-id
  myusa-youtube-client-secret
  myusa-youtube-refresh-token
)

gcloud config set project "$PROJECT_ID"
gcloud services enable \
  youtube.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com

if ! gcloud iam service-accounts describe "$YOUTUBE_SA" >/dev/null 2>&1; then
  gcloud iam service-accounts create myusa-youtube-publisher \
    --display-name="MyUSA YouTube Publisher"
fi

for i in {1..24}; do
  if gcloud iam service-accounts describe "$YOUTUBE_SA" >/dev/null 2>&1; then
    break
  fi
  sleep 5
done

gcloud iam service-accounts add-iam-policy-binding "$YOUTUBE_SA" \
  --member="serviceAccount:${DEPLOYER_SA}" \
  --role="roles/iam.serviceAccountUser" \
  --quiet >/dev/null

if ! gcloud storage buckets describe "gs://${BUCKET}" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://${BUCKET}" \
    --location="$REGION" \
    --uniform-bucket-level-access
fi

gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member="serviceAccount:${YOUTUBE_SA}" \
  --role="roles/storage.objectViewer" \
  --quiet >/dev/null

# Delete staging uploads after two days. Cloud Storage soft-delete behavior may retain
# deleted objects according to the bucket's soft-delete policy; review it in Cloud Console.
LIFECYCLE_FILE="$(mktemp)"
cat > "$LIFECYCLE_FILE" <<'JSON'
{
  "rule": [
    {
      "action": {"type": "Delete"},
      "condition": {"age": 2}
    }
  ]
}
JSON
gcloud storage buckets update "gs://${BUCKET}" --lifecycle-file="$LIFECYCLE_FILE" >/dev/null
rm -f "$LIFECYCLE_FILE"

for SECRET in "${SECRETS[@]}"; do
  if ! gcloud secrets describe "$SECRET" >/dev/null 2>&1; then
    gcloud secrets create "$SECRET" --replication-policy="automatic"
  fi
  gcloud secrets add-iam-policy-binding "$SECRET" \
    --member="serviceAccount:${YOUTUBE_SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet >/dev/null
done

echo ""
echo "MyUSA YouTube Cloud resources are ready."
echo "Runtime service account: ${YOUTUBE_SA}"
echo "Private staging bucket: gs://${BUCKET}"
echo "Secrets created (values are NOT set by this script):"
printf '  - %s\n' "${SECRETS[@]}"
echo ""
echo "Next: create a Google OAuth Desktop/Web client with YouTube Data API access,"
echo "authorize the actual MyUSA YouTube channel, then add the client ID, client secret,"
echo "and refresh token as Secret Manager secret versions. Never put them in GitHub."
