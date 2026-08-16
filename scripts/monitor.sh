#!/usr/bin/env bash
# The 2:45 beat — the live event, and the restraint.
#
#   ./scripts/monitor.sh chest_pain              expect: paged, SLA started
#   ./scripts/monitor.sh lightheaded_on_standing  expect: Escalator declines to page
#   ./scripts/monitor.sh exertional_tachycardia  expect: Watchman matches nothing
#   ./scripts/monitor.sh both                     chest_pain then the restraint case
#
# Showing only the escalation proves the fleet can panic, which is easy. The
# second one is the beat worth watching.
set -uo pipefail

G="${GATEWAY:-https://vitahome-gateway-205100594497.us-central1.run.app}"
PID="${PATIENT:-p_hero}"

b() { printf "\033[34m%s\033[0m\n" "$*"; }
d() { printf "\033[2m%s\033[0m\n" "$*"; }

audit_count() {
  curl -s --max-time 20 "$G/patient/$PID/audit?limit=500" 2>/dev/null \
    | python3 -c "import sys,json;print(len(json.load(sys.stdin)['audit']))" 2>/dev/null || echo 0
}

run_one() {
  local sc="$1"
  echo
  b "▸ $sc"
  # Remember where the trail was, so we print only what this run produced
  # rather than replaying the previous scenario's rows.
  local BEFORE; BEFORE=$(audit_count)
  curl -s --max-time 30 -X POST "$G/demo/observe?scenario=$sc&patientId=$PID" \
    | python3 -c "import sys,json;d=json.load(sys.stdin);print(f\"  watchman task {d['taskId']} · expected: {d['expect']}\")"

  for i in $(seq 1 24); do
    sleep 5
    DONE=$(curl -s --max-time 20 "$G/patient/$PID/tasks" 2>/dev/null | python3 -c "
import sys,json
t=json.load(sys.stdin)['tasks']
live=[x for x in t if x.get('agent') in ('watchman','escalator') and x.get('status') in ('pending','leased')]
print('0' if live else '1')" 2>/dev/null)
    [ "$DONE" = "1" ] && [ "$i" -gt 1 ] && break
  done

  curl -s --max-time 25 "$G/patient/$PID/audit?limit=500" | BEFORE="$BEFORE" python3 -c "
import sys,json,os
rows=json.load(sys.stdin)['audit']          # newest first
new=rows[:max(0,len(rows)-int(os.environ['BEFORE']))]
for x in reversed(new):
    if x.get('actor') not in ('watchman','escalator'): continue
    mark={'escalation':'🚨','refusal':'⚖ '}.get(x['kind'],'· ')
    if 'stood down' in x['detail']: mark='🟢'
    if 'overridden' in x['detail']: mark='⛔'
    print(f\"  {mark} {x['actor']:<10} {x['detail'][:100]}\")"
}

case "${1:-both}" in
  both) run_one chest_pain; echo; d "  ── now the harder case ──"; run_one lightheaded_on_standing;;
  all)  run_one chest_pain; run_one lightheaded_on_standing; run_one exertional_tachycardia;;
  *)    run_one "$1";;
esac
echo
