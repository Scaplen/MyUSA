#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="optimum-sound-505003-d3"
PROJECT_NUMBER="265519813462"
POOL_ID="myusa-github"
PROVIDER_ID="github"
REPO="Scaplen/MyUSA"
DEPLOYER_SA="myusa-github-deployer@${PROJECT_ID}.iam.gserviceaccount.com"
RUNTIME_SA="myusa-google-connector@${PROJECT_ID}.iam.gserviceaccount.com"
BUILD_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# Required APIs for keyless GitHub deployment and Cloud Run source builds.
gcloud config set project "$PROJECT_ID"
gcloud services enable \
  iamcredentials.googleapis.com \
  sts.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  serviceusage.googleapis.com

# Dedicated deployment identity: separate from the runtime analytics identity.
if ! gcloud iam service-accounts describe "$DEPLOYER_SA" >/dev/null 2>&1; then
  gcloud iam service-accounts create myusa-github-deployer \
    --display-name="MyUSA GitHub Cloud Run Deployer"
fi

# Newly created service accounts can take a short time to become usable by IAM APIs.
echo "Waiting for deployer service account to propagate..."
for i in {1..24}; do
  if gcloud iam service-accounts describe "$DEPLOYER_SA" >/dev/null 2>&1; then
    break
  fi
  sleep 5
  if [ "$i" -eq 24 ]; then
    echo "Service account did not become available in time." >&2
    exit 1
  fi
done

# Minimum documented project roles for source deployment.
for ROLE in roles/run.sourceDeveloper roles/serviceusage.serviceUsageConsumer; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${DEPLOYER_SA}" \
    --role="$ROLE" \
    --quiet >/dev/null
done

# Allow the deployer to attach the existing runtime service identity.
gcloud iam service-accounts add-iam-policy-binding "$RUNTIME_SA" \
  --member="serviceAccount:${DEPLOYER_SA}" \
  --role="roles/iam.serviceAccountUser" \
  --quiet >/dev/null

# Cloud Run source builds use the Compute Engine default service account unless overridden.
# The build account needs Cloud Run Builder, and the GitHub deployer must be allowed to act as it.
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="serviceAccount:${BUILD_SA}" \
  --role="roles/run.builder" \
  --quiet >/dev/null

gcloud iam service-accounts add-iam-policy-binding "$BUILD_SA" \
  --member="serviceAccount:${DEPLOYER_SA}" \
  --role="roles/iam.serviceAccountUser" \
  --quiet >/dev/null

# Create the Workload Identity pool if needed.
if ! gcloud iam workload-identity-pools describe "$POOL_ID" --location=global >/dev/null 2>&1; then
  gcloud iam workload-identity-pools create "$POOL_ID" \
    --location=global \
    --display-name="MyUSA GitHub"
fi

# Trust GitHub OIDC tokens only from Scaplen/MyUSA.
if ! gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
  --workload-identity-pool="$POOL_ID" --location=global >/dev/null 2>&1; then
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
    --location=global \
    --workload-identity-pool="$POOL_ID" \
    --display-name="GitHub Scaplen MyUSA" \
    --issuer-uri="https://token.actions.githubusercontent.com" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
    --attribute-condition="assertion.repository=='${REPO}'"
fi

# Permit only this GitHub repository to impersonate the dedicated deployer account.
gcloud iam service-accounts add-iam-policy-binding "$DEPLOYER_SA" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${REPO}" \
  --quiet >/dev/null

echo ""
echo "MyUSA GitHub -> Google Cloud keyless deployment trust is configured."
echo "Provider: projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}"
echo "Deployer: ${DEPLOYER_SA}"
echo "Repository: ${REPO}"
echo ""
echo "Future connector changes on feature/ga4-mcp-connector can deploy through GitHub Actions without service-account keys."
