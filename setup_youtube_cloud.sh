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
  myusa-youtube-setup-key
  myusa-youtube-state-secret
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

# The auth helper is the only runtime component allowed to add a refresh-token version.
gcloud secrets add-iam-policy-binding myusa-youtube-refresh-token \
  --member="serviceAccount:${YOUTUBE_SA}" \
  --role="roles/secretmanager.secretVersionAdder" \
  --quiet >/dev/null

# Create strong one-time helper secrets if they do not yet have a version.
if ! gcloud secrets versions list myusa-youtube-setup-key --filter='state=ENABLED' --format='value(name)' | grep -q .; then
  python3 -c 'import secrets; print(secrets.token_urlsafe(32))' | \
    gcloud secrets versions add myusa-youtube-setup-key --data-file=- >/dev/null
fi
if ! gcloud secrets versions list myusa-youtube-state-secret --filter='state=ENABLED' --format='value(name)' | grep -q .; then
  python3 -c 'import secrets; print(secrets.token_urlsafe(48))' | \
    gcloud secrets versions add myusa-youtube-state-secret --data-file=- >/dev/null
fi

echo ""
echo "MyUSA YouTube Cloud resources are ready."
echo "Runtime service account: ${YOUTUBE_SA}"
echo "Private staging bucket: gs://${BUCKET}"
echo "Secrets ready:"
printf '  - %s\n' "${SECRETS[@]}"
echo ""
echo "The setup key and signed-state secret were generated automatically."
echo "The OAuth client ID/secret and refresh token are intentionally not printed or stored in GitHub."
