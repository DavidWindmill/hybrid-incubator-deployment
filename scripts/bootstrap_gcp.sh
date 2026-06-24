#!/usr/bin/env bash
set -euo pipefail
PROJECT_ID=${PROJECT_ID:?Define PROJECT_ID}
REGION=${REGION:-europe-southwest1}
ARTIFACT_REPOSITORY=${ARTIFACT_REPOSITORY:-incubadora-quantum}
DEPLOYER_SA=hybrid-deployer
RUNTIME_SA=incubator-runtime

gcloud config set project "$PROJECT_ID"
gcloud services enable   run.googleapis.com   cloudbuild.googleapis.com   artifactregistry.googleapis.com   iam.googleapis.com   serviceusage.googleapis.com   logging.googleapis.com

if ! gcloud artifacts repositories describe "$ARTIFACT_REPOSITORY" --location "$REGION" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$ARTIFACT_REPOSITORY"     --repository-format docker     --location "$REGION"     --description "Imagenes de la incubadora hibrida"
fi

for account in "$DEPLOYER_SA" "$RUNTIME_SA"; do
  if ! gcloud iam service-accounts describe "$account@$PROJECT_ID.iam.gserviceaccount.com" >/dev/null 2>&1; then
    gcloud iam service-accounts create "$account"
  fi
done

DEPLOYER_EMAIL="$DEPLOYER_SA@$PROJECT_ID.iam.gserviceaccount.com"
RUNTIME_EMAIL="$RUNTIME_SA@$PROJECT_ID.iam.gserviceaccount.com"
DEFAULT_BUILD_SA="$(gcloud builds get-default-service-account --project "$PROJECT_ID")"
for role in   roles/run.admin   roles/artifactregistry.writer   roles/cloudbuild.builds.editor   roles/logging.logWriter   roles/serviceusage.serviceUsageConsumer; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID"     --member "serviceAccount:$DEPLOYER_EMAIL"     --role "$role" >/dev/null
done

gcloud iam service-accounts add-iam-policy-binding "$RUNTIME_EMAIL"   --member "serviceAccount:$DEPLOYER_EMAIL"   --role roles/iam.serviceAccountUser >/dev/null

gcloud projects add-iam-policy-binding "$PROJECT_ID"   --member "serviceAccount:$RUNTIME_EMAIL"   --role roles/logging.logWriter >/dev/null

cat <<EOF
Configuracion terminada.
Proyecto: $PROJECT_ID
Region: $REGION
Artifact Registry: $ARTIFACT_REPOSITORY
Cuenta Cloud Build: $DEPLOYER_EMAIL
Cuenta Cloud Run: $RUNTIME_EMAIL
Cuenta predeterminada de builds anidados: $DEFAULT_BUILD_SA
EOF
