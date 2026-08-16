#!/usr/bin/env bash
# The one cost lever that matters, as a switch.
#
#   ./scripts/warm.sh off    scale to zero when idle — costs ~nothing between
#                            sessions, first visitor waits on a cold start
#   ./scripts/warm.sh on     keep one instance of each service alive — instant
#                            for anyone who opens the link, ~$0.75/day
#   ./scripts/warm.sh        show the current setting
#
# Build with it off. Turn it on before submitting, and before recording.
#
# Everything else in this project is priced in fractions of a cent: a parse is a
# few thousand Gemini tokens, a booking is two FHIR writes. Two always-on Cloud
# Run instances are the only thing here that bills while nobody is using it.
set -uo pipefail

PROJECT="${PROJECT:-gen-lang-client-0109591583}"
REGION="${REGION:-us-central1}"
SERVICES="vitahome-gateway vitahome-web"

show() {
  for s in $SERVICES; do
    m=$(gcloud run services describe "$s" --project "$PROJECT" --region "$REGION" \
        --format="value(spec.template.metadata.annotations['autoscaling.knative.dev/minScale'])" 2>/dev/null)
    printf "  %-18s min-instances=%s\n" "$s" "${m:-0}"
  done
}

case "${1:-show}" in
  on|warm|1)
    for s in $SERVICES; do
      gcloud run services update "$s" --project "$PROJECT" --region "$REGION" \
        --min-instances=1 --quiet >/dev/null 2>&1 && echo "  $s → always warm"
    done
    echo
    echo "  Judges get an instant first paint. Roughly \$0.75/day while it stays on."
    ;;
  off|cold|0)
    for s in $SERVICES; do
      gcloud run services update "$s" --project "$PROJECT" --region "$REGION" \
        --min-instances=0 --quiet >/dev/null 2>&1 && echo "  $s → scales to zero"
    done
    echo
    echo "  Near-zero between sessions. Run ./scripts/preflight.sh to warm before a demo."
    ;;
  *)
    echo "current:"; show
    echo
    echo "  ./scripts/warm.sh on    before submitting or recording"
    echo "  ./scripts/warm.sh off   while building"
    ;;
esac
