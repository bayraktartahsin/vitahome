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

# --cpu-boost is doing real work here. Without it a cold start runs ~8s and you
# end up pinning min-instances=1 to hide it, which bills ~$23/month to serve
# nobody. With it, cold start is ~0.7s and the services can sleep.
echo "▸ deploying gateway"
gcloud run deploy vitahome-gateway --source ./backend \
  --project "$PROJECT" --region "$REGION" --platform managed --allow-unauthenticated \
  --port 8080 --memory 1Gi --cpu 1 --timeout 300 --concurrency 40 \
  --min-instances 0 --max-instances 20 --cpu-boost \
  --set-env-vars "GCP_PROJECT=${PROJECT},REGION=${REGION},HC_LOCATION=${HC_LOCATION},HC_DATASET=${DATASET},HC_FHIR_STORE=${FHIR_STORE},MODEL_FAST=gemini-3.5-flash-lite,MODEL_REASON=gemini-3.7-flash,LOG_LEVEL=INFO" \
  --set-secrets "GEMINI_API_KEY=gemini-api-key:latest" --quiet

GATEWAY_URL="$(gcloud run services describe vitahome-gateway --region "$REGION" \
  --project "$PROJECT" --format='value(status.url)')"

echo "▸ deploying the Scheduler on its own service"
# Deliberately the same source and image as the gateway. Extracting an agent is
# a ROUTING change — its push subscription targets this service instead — and
# deploying it this way is what keeps that claim honest. The drill kills a
# worker here while the gateway keeps serving the console.
gcloud run deploy vitahome-scheduler --source ./backend \
  --project "$PROJECT" --region "$REGION" --platform managed --allow-unauthenticated \
  --port 8080 --memory 1Gi --cpu 1 --timeout 300 --concurrency 40 \
  --min-instances 0 --max-instances 20 --cpu-boost \
  --set-env-vars "GCP_PROJECT=${PROJECT},REGION=${REGION},HC_LOCATION=${HC_LOCATION},HC_DATASET=${DATASET},HC_FHIR_STORE=${FHIR_STORE},MODEL_FAST=gemini-3.5-flash-lite,MODEL_REASON=gemini-3.7-flash,LOG_LEVEL=INFO" \
  --set-secrets "GEMINI_API_KEY=gemini-api-key:latest" --quiet

SCHED_URL="$(gcloud run services describe vitahome-scheduler --region "$REGION" \
  --project "$PROJECT" --format='value(status.url)')"
gcloud run services update vitahome-gateway --project "$PROJECT" --region "$REGION" \
  --update-env-vars "^@^AGENT_SERVICES={\"scheduler\":\"${SCHED_URL}\"}" --quiet >/dev/null

echo "▸ deploying web"
gcloud run deploy vitahome-web --source ./web \
  --project "$PROJECT" --region "$REGION" --platform managed --allow-unauthenticated \
  --port 8080 --memory 512Mi --cpu 1 --timeout 60 \
  --min-instances 0 --max-instances 10 --cpu-boost --quiet

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
  EP="${GATEWAY_URL}"
  [ "$a" = "scheduler" ] && EP="${SCHED_URL}"
  if gcloud pubsub subscriptions create "sub-$a" \
      --topic=fleet-work --push-endpoint="${EP}/agents/${a}" \
      --message-filter="attributes.agent = \"${a}\"" \
      --ack-deadline=90 --project "$PROJECT" 2>/dev/null; then
    echo "  sub-$a created"
  else
    # Filters are immutable; endpoint and deadline are not. Converge what we can.
    gcloud pubsub subscriptions update "sub-$a" \
      --push-endpoint="${EP}/agents/${a}" \
      --ack-deadline=90 --project "$PROJECT" --quiet >/dev/null
    echo "  sub-$a updated"
  fi
done

echo "▸ Firestore index: collection-group query on task status"
# The supervisor sweeps every patient's tasks at once with a collection_group
# query. Firestore auto-indexes single fields per collection but NOT across a
# collection group, so this exemption has to be created explicitly.
#
# Skipping it does not fail loudly — the endpoint simply 500s with
# FailedPrecondition the first time anything calls it, which in this project was
# not until the supervisor was finally scheduled.
curl -s -X PATCH \
  "https://firestore.googleapis.com/v1/projects/$PROJECT/databases/(default)/collectionGroups/tasks/fields/status?updateMask=indexConfig" \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -d '{"indexConfig":{"indexes":[
        {"queryScope":"COLLECTION","fields":[{"fieldPath":"status","order":"ASCENDING"}]},
        {"queryScope":"COLLECTION","fields":[{"fieldPath":"status","order":"DESCENDING"}]},
        {"queryScope":"COLLECTION_GROUP","fields":[{"fieldPath":"status","order":"ASCENDING"}]}
      ]}}' >/dev/null
echo "  index requested (builds in the background, ~4 min)"

echo "▸ Cloud Scheduler — the supervisor sweep"
# The chaos panel writes its own AGENT_DOWN before the process exits, so the
# demo never depends on this. It is the net for a REAL crash — an OOM kill, a
# container eviction — where nothing gets the chance to write anything. Without
# it a stale lease is invisible.
#
# Five minutes, not five seconds: detection latency does not need to be tight,
# and a tighter schedule would wake a scale-to-zero service constantly for no
# benefit.
gcloud scheduler jobs create http vitahome-supervisor \
  --project "$PROJECT" --location "$REGION" \
  --schedule="*/5 * * * *" \
  --uri="${GATEWAY_URL}/supervisor/scan" \
  --http-method=POST --attempt-deadline=60s \
  --quiet 2>/dev/null \
  || gcloud scheduler jobs update http vitahome-supervisor \
       --project "$PROJECT" --location "$REGION" \
       --uri="${GATEWAY_URL}/supervisor/scan" --quiet >/dev/null
echo "  supervisor sweep every 5 min"

echo
echo "✅ VitaHome is up"
echo "   web      $WEB_URL"
echo "   gateway  $GATEWAY_URL"
echo "   health   $GATEWAY_URL/health/deep"
echo "   registry $GATEWAY_URL/registry"
