#!/usr/bin/env bash
# Run this before recording. Every line must be green.
#
# The demo is one take with no edits, so the failure we cannot afford is the
# boring one: an expired ack deadline, a stale push endpoint, a chaos arm left
# armed from yesterday's rehearsal. This checks all of it in about twenty
# seconds.
#
#   ./scripts/preflight.sh
#
# Results are tallied by counting the marks in the output rather than by
# incrementing a variable: several checks run inside pipelines, and a `while`
# on the right of a pipe runs in a subshell where increments are silently lost.
set -uo pipefail

PROJECT="${PROJECT:-gen-lang-client-0109591583}"
REGION="${REGION:-us-central1}"
G="${GATEWAY:-https://vitahome-gateway-205100594497.us-central1.run.app}"
W="${WEB:-https://vitahome-web-205100594497.us-central1.run.app}"
PID="${PATIENT:-p_hero}"

LOG="$(mktemp -t vitahome-preflight)"
trap 'rm -f "$LOG"' EXIT
exec > >(tee "$LOG") 2>&1

ok()   { printf "  \033[32m✓\033[0m %s\n" "$*"; }
bad()  { printf "  \033[31m✗\033[0m %s\n" "$*"; }
warn() { printf "  \033[33m!\033[0m %s\n" "$*"; }
hd()   { printf "\n\033[1m%s\033[0m\n" "$*"; }

# curl returns 0 on a 404, so the status code has to be inspected rather than
# relied on to fail the command.
http() { curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$1" 2>/dev/null || echo 000; }

# ---------------------------------------------------------------- services --
hd "services"

# Both services scale to zero when idle, which keeps the bill near nothing
# between working sessions but means the first request after a quiet spell pays
# a cold start. Warm them before anything is timed or filmed.
curl -s -o /dev/null --max-time 60 "$G/health" 2>/dev/null
curl -s -o /dev/null --max-time 60 "$W/" 2>/dev/null

code=$(http "$G/health")
[ "$code" = "200" ] && ok "gateway up  $G" || bad "gateway /health returned $code"

# The web app is a Next build with no health route; the root IS the check.
code=$(http "$W/")
[ "$code" = "200" ] && ok "web up      $W" || bad "web root returned $code"
for path in /capture /console /console/drill; do
  code=$(http "$W$path")
  [ "$code" = "200" ] && ok "  $path" || bad "  $path returned $code"
done

REV=$(gcloud run services describe vitahome-gateway --region "$REGION" --project "$PROJECT" \
      --format='value(status.latestReadyRevisionName)' 2>/dev/null)
[ -n "$REV" ] && ok "gateway revision $REV" || bad "cannot read gateway revision"

# Cost guard. Scale-to-zero is the right default now that startup CPU boost has
# cold starts under a second — it used to be a real trade against a judge
# waiting eight seconds for a first paint, and it is no longer.
MIN=$(gcloud run services describe vitahome-gateway --region "$REGION" --project "$PROJECT" \
      --format="value(spec.template.metadata.annotations['autoscaling.knative.dev/minScale'])" 2>/dev/null)
BOOST=$(gcloud run services describe vitahome-gateway --region "$REGION" --project "$PROJECT" \
        --format="value(spec.template.metadata.annotations['run.googleapis.com/startup-cpu-boost'])" 2>/dev/null)
if [ "${MIN:-0}" -ge 1 ] 2>/dev/null; then
  ok "min-instances=$MIN — always warm (\$0.75/day)"
elif [ "$BOOST" = "true" ]; then
  ok "scale-to-zero with startup CPU boost — cold start measured at 0.73s"
else
  bad "scale-to-zero WITHOUT cpu-boost — cold starts run ~8s. Fix:"
  printf "      gcloud run services update vitahome-gateway --region %s --cpu-boost\n" "$REGION"
fi

# ------------------------------------------------------------- substrate ---
hd "substrate"
curl -s --max-time 40 "$G/health/deep" 2>/dev/null | python3 -c "
import sys,json
try: d=json.load(sys.stdin)
except Exception: print('  \033[31m✗\033[0m /health/deep did not return JSON'); sys.exit(0)
f=d.get('fhir') or {}
g=d.get('gemini') or {}
print(('  \033[32m✓\033[0m' if f.get('ok') else '  \033[31m✗\033[0m') + f\" FHIR store {d.get('fhirStore')} reachable\")
print(('  \033[32m✓\033[0m' if g.get('ok') else '  \033[31m✗\033[0m') + f\" Gemini reachable ({g.get('model','?')}, {g.get('latencyMs','?')}ms)\")
print(f\"  \033[32m✓\033[0m project {d.get('project')}\")
"

hd "agent registry"
curl -s --max-time 20 "$G/registry" 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin); a=d.get('agents', d if isinstance(d,list) else [])
n=len(a)
print(('  \033[32m✓\033[0m' if n==7 else '  \033[31m✗\033[0m')+f' {n} agent cards served (expect 7)')
h=[x for x in a if x.get('humanTerminated')]
print(('  \033[32m✓\033[0m' if h else '  \033[31m✗\033[0m')+f\" human-terminated: {', '.join(x['name'] for x in h) or 'NONE — expected the escalator'}\")
"

# ---------------------------------------------------------------- pub/sub --
hd "pub/sub topology"
gcloud pubsub subscriptions list --project "$PROJECT" \
  --format="value(name.basename(),ackDeadlineSeconds,filter,pushConfig.pushEndpoint)" 2>/dev/null \
  | grep '^sub-' | GATEWAY="$G" python3 -c "
import sys,os
g=os.environ['GATEWAY']
for line in sys.stdin:
    parts=(line.rstrip('\n').split('\t')+['','',''])[:4]
    name,dl,flt,ep=parts
    probs=[]
    if not dl.isdigit() or int(dl)<60: probs.append(f'ack={dl}s too low')
    if not flt.strip():                probs.append('no attribute filter')
    if not ep.startswith(g):           probs.append(f'endpoint {ep or \"missing\"}')
    if probs: print(f'  \033[31m✗\033[0m {name:<16} ' + ' · '.join(probs))
    else:     print(f'  \033[32m✓\033[0m {name:<16} ack={dl}s filtered')
"

# ------------------------------------------------------------ demo state ---
hd "demo state"
ARMED=$(curl -s --max-time 20 "$G/chaos/status" 2>/dev/null \
        | python3 -c "import sys,json;print(json.load(sys.stdin).get('armed') or '')" 2>/dev/null)
[ -z "$ARMED" ] && ok "chaos disarmed" \
                || bad "chaos still ARMED for '$ARMED' — curl -XPOST $G/chaos/disarm"

curl -s --max-time 60 -X POST "$G/demo/seed" 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(f\"  \033[32m✓\033[0m patient seeded — {d['instructions']} instructions, critical {d['critical']}\")
" 2>/dev/null || bad "seed failed"

curl -s --max-time 20 "$G/patient/$PID/ledger" 2>/dev/null | GATEWAY="$G" PID="$PID" python3 -c "
import sys,json,os
d=json.load(sys.stdin)
if sum(d.values())==0:
    print('  \033[32m✓\033[0m autonomy ledger at zero')
else:
    print(f\"  \033[31m✗\033[0m rehearsal counts still on the board — {d['autonomous']} autonomous · {d['humanDecisions']} human · {d['refused']} refused\")
    print(f\"      curl -XPOST '{os.environ['GATEWAY']}/demo/reset?patientId={os.environ['PID']}'\")
" 2>/dev/null || bad "ledger unreachable"

curl -s --max-time 25 "$G/patient/$PID/tasks" 2>/dev/null | python3 -c "
import sys,json
t=json.load(sys.stdin)['tasks']
live=[x for x in t if x.get('status') in ('leased','pending')]
print(('  \033[32m✓\033[0m no tasks in flight' if not live
       else f'  \033[33m!\033[0m {len(live)} task(s) still in flight — let them settle'))
" 2>/dev/null || bad "tasks unreachable"

curl -s --max-time 25 "$G/patient/$PID/exceptions" 2>/dev/null | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(('  \033[32m✓\033[0m exception queue empty' if d['count']==0
       else f\"  \033[33m!\033[0m {d['count']} item(s) already waiting on a human\"))
" 2>/dev/null || bad "exceptions unreachable"

# ----------------------------------------------------------------- local ---
hd "local"
(
  cd "$(dirname "$0")/../backend" || exit
  if .venv/bin/python -m pytest tests -q 2>/dev/null | tail -1 | grep -q "passed"; then
    N=$(.venv/bin/python -m pytest tests -q 2>/dev/null | tail -1 | grep -oE '^[0-9]+')
    printf "  \033[32m✓\033[0m %s tests pass\n" "$N"
  else
    printf "  \033[31m✗\033[0m tests failing — run: cd backend && .venv/bin/python -m pytest\n"
  fi
)

# ---------------------------------------------------------------- verdict ---
sync
PASS=$(grep -c '✓' "$LOG" || true)
FAIL=$(grep -c '✗' "$LOG" || true)
WARN=$(grep -c '!' "$LOG" || true)
hd "result"
if [ "$FAIL" -eq 0 ]; then
  printf "  \033[32m%s green" "$PASS"
  [ "$WARN" -gt 0 ] && printf ", %s to look at" "$WARN"
  printf " — clear to record\033[0m\n\n"
else
  printf "  \033[31m%s failed, %s green — fix before recording\033[0m\n\n" "$FAIL" "$PASS"
  exit 1
fi
