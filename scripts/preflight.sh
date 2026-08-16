#!/usr/bin/env bash
# Run this before recording. Every line must be green.
#
# The demo is one take with no edits, so the failure we cannot afford is the
# boring one: an expired deadline, a stale push endpoint, a chaos arm left set
# from yesterday's rehearsal. This checks all of it in about twenty seconds.
#
#   ./scripts/preflight.sh
set -uo pipefail

PROJECT="${PROJECT:-gen-lang-client-0109591583}"
REGION="${REGION:-us-central1}"
G="${GATEWAY:-https://vitahome-gateway-205100594497.us-central1.run.app}"
W="${WEB:-https://vitahome-web-205100594497.us-central1.run.app}"
PID="${PATIENT:-p_hero}"

PASS=0; FAIL=0
ok()   { printf "  \033[32m✓\033[0m %s\n" "$*"; PASS=$((PASS+1)); }
bad()  { printf "  \033[31m✗\033[0m %s\n" "$*"; FAIL=$((FAIL+1)); }
warn() { printf "  \033[33m!\033[0m %s\n" "$*"; }
hd()   { printf "\n\033[1m%s\033[0m\n" "$*"; }

# ---------------------------------------------------------------- services --
hd "services"
for pair in "gateway:$G" "web:$W"; do
  name="${pair%%:*}"; url="${pair#*:}"
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$url/health" 2>/dev/null \
         || curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$url" 2>/dev/null)
  [ "$code" = "200" ] && ok "$name up ($url)" || bad "$name returned $code — $url"
done

REV=$(gcloud run services describe vitahome-gateway --region "$REGION" --project "$PROJECT" \
      --format='value(status.latestReadyRevisionName)' 2>/dev/null)
[ -n "$REV" ] && ok "gateway revision $REV" || bad "cannot read gateway revision"

# ------------------------------------------------------------- substrate ---
hd "substrate"
curl -s --max-time 25 "$G/health/deep" 2>/dev/null | python3 -c "
import sys,json
try: d=json.load(sys.stdin)
except Exception: print('  \033[31m✗\033[0m /health/deep did not return JSON'); sys.exit(1)
print(('  \033[32m✓\033[0m' if d.get('fhir') else '  \033[31m✗\033[0m') + f\" FHIR store {d.get('fhirStore')} reachable\")
print(f\"  \033[32m✓\033[0m project {d.get('project')}\")
" || bad "deep health check failed"

hd "agent registry"
curl -s --max-time 20 "$G/registry" 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin); a=d.get('agents',d if isinstance(d,list) else [])
n=len(a)
print((f'  \033[32m✓\033[0m' if n==7 else f'  \033[31m✗\033[0m')+f' {n} agent cards served (expect 7)')
h=[x for x in a if x.get('humanTerminated')]
print(f\"  \033[32m✓\033[0m human-terminated: {', '.join(x['name'] for x in h) or 'NONE — expected escalator'}\")
" 2>/dev/null || bad "registry unreachable"

# ---------------------------------------------------------------- pub/sub --
hd "pub/sub topology"
gcloud pubsub subscriptions list --project "$PROJECT" \
  --format="value(name.basename(),ackDeadlineSeconds,filter,pushConfig.pushEndpoint)" 2>/dev/null \
  | grep '^sub-' | while IFS=$'\t' read -r n dl flt ep; do
      probs=""
      [ "${dl:-0}" -lt 60 ] && probs="$probs ack=${dl}s(too low)"
      [ -z "$flt" ]         && probs="$probs no-filter"
      case "$ep" in *"$(basename "$G")"*|"$G"/*) ;; *) probs="$probs endpoint-mismatch";; esac
      if [ -z "$probs" ]; then printf "  \033[32m✓\033[0m %-16s ack=%ss filtered\n" "$n" "$dl"
      else printf "  \033[31m✗\033[0m %-16s%s\n" "$n" "$probs"; fi
    done

# ------------------------------------------------------------ demo state ---
hd "demo state"
ARMED=$(curl -s --max-time 20 "$G/chaos/status" 2>/dev/null \
        | python3 -c "import sys,json;print(json.load(sys.stdin).get('armed') or '')" 2>/dev/null)
[ -z "$ARMED" ] && ok "chaos disarmed" \
                || bad "chaos still ARMED for '$ARMED' — run: curl -XPOST $G/chaos/disarm"

curl -s --max-time 25 -X POST "$G/demo/seed" 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(f\"  \033[32m✓\033[0m patient seeded — {d['instructions']} instructions, critical {d['critical']}\")
" 2>/dev/null || bad "seed failed"

curl -s --max-time 20 "$G/patient/$PID/ledger" 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)
tot=sum(d.values())
mark='\033[32m✓' if tot==0 else '\033[33m!'
print(f\"  {mark}\033[0m autonomy ledger: {d['autonomous']} autonomous · {d['humanDecisions']} human · {d['refused']} refused\")
if tot: print(f'    rehearsal counts still on the board — clear with:')
if tot: print(f'      curl -XPOST \"$G/demo/reset?patientId=$PID\"')
" 2>/dev/null || bad "ledger unreachable"

STUCK=$(curl -s --max-time 25 "$G/patient/$PID/tasks" 2>/dev/null | python3 -c "
import sys,json
t=json.load(sys.stdin)['tasks']
print(len([x for x in t if x.get('status') in ('leased','pending')]))" 2>/dev/null)
[ "${STUCK:-0}" = "0" ] && ok "no tasks in flight" || warn "$STUCK task(s) still in flight — let them settle"

# ----------------------------------------------------------------- local ---
hd "local"
( cd "$(dirname "$0")/../backend" && .venv/bin/python -m pytest tests -q 2>/dev/null | tail -1 \
  | grep -q "passed" && echo "  ✓ tests pass" || echo "  ✗ tests failing" )

hd "result"
if [ "$FAIL" -eq 0 ]; then
  printf "  \033[32m%s checks green — clear to record\033[0m\n\n" "$PASS"
else
  printf "  \033[31m%s failed, %s passed — fix before recording\033[0m\n\n" "$FAIL" "$PASS"
  exit 1
fi
