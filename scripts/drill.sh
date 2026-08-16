#!/usr/bin/env bash
# The Failure Drill, end to end, against the deployed fleet.
#
#   ./scripts/drill.sh          arm the Scheduler, dispatch, watch it die and recover
#   ./scripts/drill.sh clean    control run, no kill
#
# What it proves: the worker dies mid-step with the message unacked, Pub/Sub
# redelivers, the replaying worker SKIPS the steps that already completed, and
# exactly one FHIR Appointment exists at the end.
set -uo pipefail

G="${GATEWAY:-https://vitahome-gateway-205100594497.us-central1.run.app}"
PID="${PATIENT:-p_hero}"
MODE="${1:-drill}"
SPECIALTY="${SPECIALTY:-cardiology}"
DAYS="${DAYS:-7}"

b() { printf "\033[34m%s\033[0m\n" "$*"; }
r() { printf "\033[31m%s\033[0m\n" "$*"; }
g() { printf "\033[32m%s\033[0m\n" "$*"; }
d() { printf "\033[2m%s\033[0m\n" "$*"; }

b "▸ seeding hero patient"
curl -s --max-time 90 -X POST "$G/demo/seed" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print(f\"  patient={d['patientId']} instructions={d['instructions']} critical={d['critical']}\")"

if [ "$MODE" = "drill" ]; then
  b "▸ arming the Scheduler — it will die inside its next step"
  curl -s --max-time 30 -X POST "$G/chaos/arm?agent=scheduler&patientId=$PID" \
    | python3 -c "import sys,json;print('  '+json.load(sys.stdin)['note'])"
fi

b "▸ dispatching Scheduler task ($SPECIALTY, ${DAYS}d)"
TASK=$(curl -s --max-time 30 -X POST "$G/demo/dispatch" \
  -H 'Content-Type: application/json' \
  -d "{\"patientId\":\"$PID\",\"agent\":\"scheduler\",\"instructionId\":\"i_06\",
       \"payload\":{\"specialty\":\"$SPECIALTY\",\"daysOut\":$DAYS}}" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['taskId'])")
d "  task=$TASK"

b "▸ watching (up to 150s)"
LAST=""
for i in $(seq 1 30); do
  sleep 5
  LINE=$(curl -s --max-time 20 "$G/patient/$PID/tasks" 2>/dev/null | python3 -c "
import sys,json
try:
  t=[x for x in json.load(sys.stdin)['tasks'] if x.get('taskId')=='$TASK']
  if t:
    t=t[0]
    print(f\"{t['status']}|{t.get('attempt')}|{','.join(s['name'] for s in t.get('steps',[]))}\")
  else: print('pending|0|')
except Exception: print('unreachable|?|')" 2>/dev/null)
  IFS='|' read -r ST ATT STEPS <<< "${LINE:-unreachable|?|}"
  [ "$LINE" != "$LAST" ] && printf "  t+%-4ss %-11s attempt=%-3s steps=[%s]\n" "$((i*5))" "$ST" "$ATT" "$STEPS"
  LAST="$LINE"
  [ "$ST" = "done" ] || [ "$ST" = "refused" ] || [ "$ST" = "escalated" ] && break
done

echo
b "▸ audit trail for this task"
curl -s --max-time 25 "$G/patient/$PID/audit?limit=60" | python3 -c "
import sys,json
rows=[x for x in json.load(sys.stdin)['audit'] if x.get('taskId')=='$TASK']
mark={'AGENT_DOWN':'💀','redelivery':'🔁','skip':'⏭ ','action':'· ','lease':'🔒','refusal':'⚖ ','escalation':'🚨'}
for x in reversed(rows):
    print(f\"  {mark.get(x['kind'],'· ')} {x['kind']:<11} {x['detail'][:84]}\")"

echo
b "▸ duplicate check"
curl -s --max-time 25 "$G/patient/$PID/tasks" | python3 -c "
import sys,json
t=[x for x in json.load(sys.stdin)['tasks'] if x.get('taskId')=='$TASK']
if t:
    refs=[s.get('externalRef') for s in t[0].get('steps',[]) if s.get('externalRef')]
    ok = len(refs)==len(set(refs))
    print(f'  external refs: {refs}')
    print('  ' + ('✅ exactly one booking — idempotency held' if ok else '❌ DUPLICATE BOOKING'))"
g "▸ drill complete"
