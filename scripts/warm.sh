#!/usr/bin/env bash
# Keep an instance alive, or don't.
#
#   ./scripts/warm.sh off    scale to zero when idle  (default, ~$0/month)
#   ./scripts/warm.sh on     keep one instance alive  (~$0.75/day)
#   ./scripts/warm.sh        show the current setting
#
# **You almost certainly want "off".**
#
# Two always-on instances were costing roughly $23/month to serve nobody. The
# reason to keep them was cold starts, which were around eight seconds — long
# enough that a judge opening the link would notice.
#
# Startup CPU boost fixed that. Cloud Run gives the container full CPU while it
# boots instead of the throttled share an idle instance normally gets, and it
# costs nothing extra. Measured after ten minutes idle:
#
#     gateway   cold 0.73s    warm 0.43s
#     web       cold 0.80s    warm 0.34s
#
# Sub-second from a standing start. So the trade this script exists to manage
# has mostly evaporated: turn it on for a recording if you want the last 300ms,
# but the honest answer is that the app costs nothing to leave running.
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
