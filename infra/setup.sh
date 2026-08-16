#!/usr/bin/env bash
# VitaHome — one-command environment provisioning.
#
# Recreates every Google Cloud resource the fleet needs, from zero, in a fresh
# project. Idempotent: safe to re-run.
#
#   ./infra/setup.sh <PROJECT_ID> [REGION]
#
# Requires: gcloud (authenticated), a billing account linked to the project,
# and GEMINI_API_KEY exported in your shell.
set -euo pipefail

PROJECT="${1:?usage: setup.sh <PROJECT_ID> [REGION]}"
REGION="${2:-us-central1}"
HC_LOCATION="us-central1"        # Healthcare API availability
DATASET="vitahome"
FHIR_STORE="clinical"

echo "▸ project=$PROJECT region=$REGION"
gcloud config set project "$PROJECT" >/dev/null

echo "▸ enabling APIs (free until used)"
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  firestore.googleapis.com \
  healthcare.googleapis.com \
  pubsub.googleapis.com \
  cloudtasks.googleapis.com \
  cloudscheduler.googleapis.com \
  secretmanager.googleapis.com \
  aiplatform.googleapis.com \
  texttospeech.googleapis.com \
  iam.googleapis.com \
  --project "$PROJECT"

echo "▸ Firestore (native)"
gcloud firestore databases create --location=nam5 --type=firestore-native \
  --project "$PROJECT" 2>/dev/null || echo "  already exists"

echo "▸ Healthcare dataset + FHIR R4 store"
gcloud healthcare datasets create "$DATASET" --location="$HC_LOCATION" \
  --project "$PROJECT" 2>/dev/null || echo "  dataset exists"
gcloud healthcare fhir-stores create "$FHIR_STORE" --dataset="$DATASET" \
  --location="$HC_LOCATION" --version=R4 --project "$PROJECT" 2>/dev/null \
  || echo "  fhir store exists"

echo "▸ Pub/Sub topics"
for t in fleet-work vitals-sim; do
  gcloud pubsub topics create "$t" --project "$PROJECT" 2>/dev/null || echo "  $t exists"
done

echo "▸ secret: gemini-api-key"
if ! gcloud secrets describe gemini-api-key --project "$PROJECT" >/dev/null 2>&1; then
  printf '%s' "${GEMINI_API_KEY:?export GEMINI_API_KEY first}" \
    | gcloud secrets create gemini-api-key --data-file=- --project "$PROJECT"
fi
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"
SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
gcloud secrets add-iam-policy-binding gemini-api-key \
  --member="serviceAccount:${SA}" --role=roles/secretmanager.secretAccessor \
  --project "$PROJECT" >/dev/null
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member="serviceAccount:${SA}" --role=roles/healthcare.fhirResourceEditor >/dev/null

echo "▸ deploying gateway"
gcloud run deploy vitahome-gateway --source ./backend \
  --project "$PROJECT" --region "$REGION" --platform managed --allow-unauthenticated \
  --port 8080 --memory 1Gi --cpu 1 --timeout 300 --concurrency 40 \
  --min-instances 1 --max-instances 10 \
  --set-env-vars "GCP_PROJECT=${PROJECT},REGION=${REGION},HC_LOCATION=${HC_LOCATION},HC_DATASET=${DATASET},HC_FHIR_STORE=${FHIR_STORE},MODEL_FAST=gemini-3.5-flash-lite,MODEL_REASON=gemini-3.7-flash,LOG_LEVEL=INFO" \
  --set-secrets "GEMINI_API_KEY=gemini-api-key:latest" --quiet

GATEWAY_URL="$(gcloud run services describe vitahome-gateway --region "$REGION" \
  --project "$PROJECT" --format='value(status.url)')"

echo "▸ deploying web"
gcloud run deploy vitahome-web --source ./web \
  --project "$PROJECT" --region "$REGION" --platform managed --allow-unauthenticated \
  --port 8080 --memory 512Mi --cpu 1 --timeout 60 \
  --min-instances 1 --max-instances 10 --quiet

WEB_URL="$(gcloud run services describe vitahome-web --region "$REGION" \
  --project "$PROJECT" --format='value(status.url)')"

echo "▸ Pub/Sub push subscriptions → agent endpoints"
# One subscription per agent on a single topic, separated by an attribute
# filter. This is the decoupling: dispatch.py publishes with agent="scheduler"
# and never knows what a scheduler is or where it runs.
#
# ack-deadline is 90s, comfortably above the slowest real task (the FHIR write
# path, plus the deliberate demo window in the Failure Drill). Set it too low
# and Pub/Sub redelivers a task that is still running — survivable, because the
# ledger skips completed steps, but it muddies the attempt counter.
for a in reconciler scheduler pharmacist watchman coach escalator; do
  if gcloud pubsub subscriptions create "sub-$a" \
      --topic=fleet-work --push-endpoint="${GATEWAY_URL}/agents/${a}" \
      --message-filter="attributes.agent = \"${a}\"" \
      --ack-deadline=90 --project "$PROJECT" 2>/dev/null; then
    echo "  sub-$a created"
  else
    # Filters are immutable; endpoint and deadline are not. Converge what we can.
    gcloud pubsub subscriptions update "sub-$a" \
      --push-endpoint="${GATEWAY_URL}/agents/${a}" \
      --ack-deadline=90 --project "$PROJECT" --quiet >/dev/null
    echo "  sub-$a updated"
  fi
done

echo
echo "✅ VitaHome is up"
echo "   web      $WEB_URL"
echo "   gateway  $GATEWAY_URL"
echo "   health   $GATEWAY_URL/health/deep"
echo "   registry $GATEWAY_URL/registry"
