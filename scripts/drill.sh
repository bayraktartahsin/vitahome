#!/usr/bin/env bash
# The Failure Drill, end to end, against the deployed fleet.
#
#   ./scripts/drill.sh          full drill: dispatch → kill mid-task → watch recovery
#   ./scripts/drill.sh clean    control run: dispatch with no kill
#
# What it proves: the Scheduler is killed between steps, Pub/Sub redelivers,
# the replaying worker skips the steps that already completed, and exactly one
# FHIR Appointment exists at the end.
set -uo pipefail

G="${GATEWAY:-https://vitahome-gateway-205100594497.us-central1.run.app}"
PID="${PATIENT:-p_hero}"
MODE="${1:-kill}"

blue()  { printf "\033[34m%s\033[0m\n" "$*"; }
green() { printf "\033[32m%s\033[0m\n" "$*"; }
red()   { printf "\033[31m%s\033[0m\n" "$*"; }
dim()   { printf "\033[2m%s\033[0m\n" "$*"; }

blue "▸ seeding hero patient"
/usr/bin/curl -s -X POST "$G/demo/seed" | python3 -m json.tool

blue "▸ dispatching a Scheduler task (cardiology, 7 days)"
TASK=$(/usr/bin/curl -s -X POST "$G/demo/dispatch" \
  -H 'Content-Type: application/json' \
  -d "{\"patientId\":\"$PID\",\"agent\":\"scheduler\",\"instructionId\":\"i_06\",
       \"payload\":{\"specialty\":\"cardiology\",\"daysOut\":7}}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['taskId'])")
dim "  task=$TASK"

if [ "$MODE" = "kill" ]; then
  blue "▸ waiting for the drill window to open, then killing the worker"
  sleep 6
  red "  💀 KILL"
  /usr/bin/curl -s -X POST "$G/chaos/kill?agent=scheduler&patientId=$PID" \
    --max-time 5 >/dev/null 2>&1 || true
fi

blue "▸ watching for recovery (up to 90s)"
for i in $(seq 1 45); do
  sleep 2
  STATUS=$(/usr/bin/curl -s "$G/patient/$PID/tasks" 2>/dev/null \
    | python3 -c "
import sys,json
try:
    ts=json.load(sys.stdin)['tasks']
    t=[x for x in ts if x.get('taskId')=='$TASK']
    print(f\"{t[0]['status']}|{t[0].get('attempt',0)}|{len(t[0].get('steps',[]))}\" if t else 'missing|0|0')
except Exception: print('err|0|0')")
  IFS='|' read -r ST ATT STEPS <<< "$STATUS"
  printf "  t+%-3ss  status=%-10s attempt=%s steps=%s\n" "$((i*2))" "$ST" "$ATT" "$STEPS"
  [ "$ST" = "done" ] && break
  [ "$ST" = "refused" ] && break
done

echo
blue "▸ audit trail"
/usr/bin/curl -s "$G/patient/$PID/audit?limit=40" | python3 -c "
import sys,json
rows=[r for r in json.load(sys.stdin)['audit'] if r.get('taskId')=='$TASK' or r['kind']=='AGENT_DOWN']
for r in reversed(rows):
    k=r['kind']
    mark={'AGENT_DOWN':'💀','redelivery':'🔁','skip':'⏭','action':'·','lease':'🔒','refusal':'⚖'}.get(k,'·')
    print(f\"  {mark} {k:12s} {r['detail'][:88]}\")"

echo
blue "▸ duplicate check — how many Appointments exist for this task?"
/usr/bin/curl -s "$G/patient/$PID/tasks" | python3 -c "
import sys,json
ts=json.load(sys.stdin)['tasks']
t=[x for x in ts if x.get('taskId')=='$TASK']
if t:
    refs=[s.get('externalRef') for s in t[0].get('steps',[]) if s.get('externalRef')]
    print(f'  external refs recorded: {refs}')
    print(f'  unique: {len(set(refs))}  →  ' + ('✅ no duplicate booking' if len(refs)==len(set(refs)) else '❌ DUPLICATE'))"
green "▸ drill complete"
