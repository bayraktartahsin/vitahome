#!/usr/bin/env bash
# The whole system, end to end, asserting on every claim the demo makes.
#
#   ./scripts/fullrun.sh          everything except the 200-fleet storm (~4 min)
#   ./scripts/fullrun.sh --storm  including it (~7 min)
#
# preflight checks that the pieces are *up*. This checks that they are *right*:
# every beat runs, and every assertion is something a judge could challenge.
#
# Exits non-zero if any check fails, so it can gate a recording.
set -uo pipefail

G="${GATEWAY:-https://vitahome-gateway-205100594497.us-central1.run.app}"
W="${WEB:-https://vitahome-web-205100594497.us-central1.run.app}"
PID="${PATIENT:-p_hero}"
STORM=0; [ "${1:-}" = "--storm" ] && STORM=1

PASS=0; FAIL=0
ok()  { printf "  \033[32m✓\033[0m %s\n" "$*"; PASS=$((PASS+1)); }
bad() { printf "  \033[31m✗\033[0m %s\n" "$*"; FAIL=$((FAIL+1)); }
hd()  { printf "\n\033[1m▸ %s\033[0m\n" "$*"; }
info(){ printf "    \033[2m%s\033[0m\n" "$*"; }

# assert <label> <actual> <expected>
eq() { [ "$2" = "$3" ] && ok "$1" || bad "$1 (got '$2', want '$3')"; }
# assert <label> <haystack> contains <needle>
has() { case "$2" in *"$3"*) ok "$1";; *) bad "$1 (missing '$3')";; esac; }

jq_() { python3 -c "import sys,json;d=json.load(sys.stdin);$1" 2>/dev/null; }

# ---------------------------------------------------------------- warm up ---
hd "warming (services scale to zero)"
# The FIRST request after a deploy pulls the container image and is not a
# representative cold start; the one after it is. Report both, gate on the
# second.
T1=$(curl -s -o /dev/null -w '%{time_total}' --max-time 90 "$G/health")
T2=$(curl -s -o /dev/null -w '%{time_total}' --max-time 30 "$G/health")
info "first request ${T1}s (image pull if freshly deployed) · next ${T2}s"
python3 -c "import sys;sys.exit(0 if float('$T2')<2 else 1)" \
  && ok "service responds in under 2s" || bad "still ${T2}s after warm-up"
curl -s -o /dev/null --max-time 90 "$W/"

# ------------------------------------------------------------- reset/seed ---
hd "clean slate"
curl -s --max-time 60 -X POST "$G/demo/reset?patientId=$PID" >/dev/null
S=$(curl -s --max-time 90 -X POST "$G/demo/seed")
eq "patient seeded" "$(echo "$S" | jq_ "print(d['instructions'])")" "12"
has "the fatal instruction is flagged CRITICAL" "$(echo "$S" | jq_ "print(d['critical'])")" "i_02"
L=$(curl -s "$G/patient/$PID/ledger")
eq "ledger at zero" "$(echo "$L" | jq_ "print(sum(d.values()))")" "0"

# ------------------------------------------------------- 1. the parse ------
hd "beat 0:30 — photograph the document"
DOC=$(curl -s "$G/patient/$PID/plan" | python3 -c "
import sys,json;print(json.dumps({'patientId':'$PID','documentText':json.load(sys.stdin)['carePlan']['sourceDocument']}))")
P=$(echo "$DOC" | curl -s --max-time 120 -X POST "$G/capture" -H 'Content-Type: application/json' --data-binary @-)
MS=$(echo "$P" | jq_ "print(d['latencyMs'])")
TOP=$(echo "$P" | jq_ "print(d['instructions'][0]['criticality'])")
NCRIT=$(echo "$P" | jq_ "print(d['counts']['critical'])")
info "parsed in ${MS}ms on $(echo "$P" | jq_ "print(d['model'])")"
eq "hardest instruction is first" "$TOP" "CRITICAL"
python3 -c "import sys;sys.exit(0 if 1<=int('$NCRIT')<=4 else 1)" \
  && ok "criticality is calibrated ($NCRIT critical, not all of them)" \
  || bad "criticality miscalibrated — $NCRIT flagged CRITICAL"
echo "$P" | jq_ "
i=[x for x in d['instructions'] if 'icagrelor' in x['text']][0]
print('OK' if i['criticality']=='CRITICAL' and i.get('why') else 'NO')" | grep -q OK \
  && ok "ticagrelor caught, with a plain-language reason" \
  || bad "ticagrelor line not flagged with a rationale"
echo "$P" | jq_ "
bad=[x for x in d['instructions'] if not (1<=x['lineNo']<=30)]
print('OK' if not bad else 'NO')" | grep -q OK \
  && ok "every line number points into the document" || bad "line numbers out of range"

# --------------------------------------------- 2. the refusal + spread -----
hd "beat 1:30 — the refusal, and whether it travels"
curl -s -X POST "$G/demo/dispatch" -H 'Content-Type: application/json' \
  -d "{\"patientId\":\"$PID\",\"agent\":\"reconciler\"}" >/dev/null
for i in $(seq 1 20); do sleep 5
  E=$(curl -s "$G/patient/$PID/exceptions"); C=$(echo "$E" | jq_ "print(d['count'])")
  [ "${C:-0}" -ge 1 ] && break
done
has "Reconciler refused on the contradiction" \
    "$(echo "$E" | jq_ "print(d['exceptions'][0]['question'])")" "mlodipine"
echo "$E" | jq_ "
o=d['exceptions'][0]['options']
print('OK' if len(o)>=3 and any('line' in x.lower() or 'i_0' in x for x in o) else 'NO')" \
  | grep -q OK && ok "both readings handed over, each citing its source" \
  || bad "refusal did not carry both readings with sources"

curl -s -X POST "$G/demo/dispatch" -H 'Content-Type: application/json' \
  -d "{\"patientId\":\"$PID\",\"agent\":\"pharmacist\"}" >/dev/null
for i in $(seq 1 20); do sleep 5
  PL=$(curl -s "$G/patient/$PID/plan"); N=$(echo "$PL" | jq_ "print(len((d.get('doseSchedule') or {}).get('doses') or []))")
  [ "${N:-0}" -ge 1 ] && break
done
info "scheduled $N drugs at real clock times"
echo "$PL" | jq_ "
s=d['doseSchedule']; held=[h['drug'] for h in s.get('unresolved') or []]
print('OK' if any('mlodipine' in h for h in held) else 'NO:'+str(held))" \
  | grep -q OK && ok "Pharmacist inherited the refusal — amlodipine HELD" \
  || bad "the disputed drug was scheduled anyway"
echo "$PL" | jq_ "
import re
t=[x for dd in d['doseSchedule']['doses'] for x in dd['times']]
print('OK' if t and all(re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d',x) for x in t) else 'NO')" \
  | grep -q OK && ok "every dose time is a valid clock time" || bad "malformed dose times"

curl -s -X POST "$G/demo/dispatch" -H 'Content-Type: application/json' \
  -d "{\"patientId\":\"$PID\",\"agent\":\"coach\"}" >/dev/null
for i in $(seq 1 16); do sleep 5
  PL=$(curl -s "$G/patient/$PID/plan"); Q=$(echo "$PL" | jq_ "print((d.get('openCheckIn') or {}).get('question') or '')")
  [ -n "$Q" ] && break
done
[ -n "$Q" ] && ok "Coach asked one question" || bad "Coach produced no question"
info "\"$Q\""

# ----------------------------------------------------- 3. voice -----------
hd "voice"
CODE=$(curl -s -o /tmp/vh-fullrun.wav -w '%{http_code}' --max-time 120 "$G/patient/$PID/checkin/audio")
if [ "$CODE" = "200" ]; then
  SZ=$(wc -c < /tmp/vh-fullrun.wav)
  file /tmp/vh-fullrun.wav | grep -q "WAVE audio" \
    && ok "check-in read aloud — valid WAV, ${SZ} bytes" || bad "audio is not a valid WAV"
else
  bad "TTS returned $CODE"
fi

# ------------------------------------------- 4. escalate + restraint ------
hd "beat 2:45 — escalation, then restraint"
curl -s -X POST "$G/demo/observe?scenario=chest_pain&patientId=$PID" >/dev/null
for i in $(seq 1 24); do sleep 5
  E=$(curl -s "$G/patient/$PID/exceptions")
  echo "$E" | jq_ "print(any(x['kind']=='escalated' for x in d['exceptions']))" | grep -q True && break
done
ESC=$(echo "$E" | jq_ "
x=[y for y in d['exceptions'] if y['kind']=='escalated']
print(json.dumps(x[0]) if x else '{}')")
has "chest pain paged a clinician" "$(echo "$ESC" | jq_ "print(d.get('urgency',''))")" "emergency"
eq "a 5-minute SLA clock started" "$(echo "$ESC" | jq_ "print(d.get('slaSeconds'))")" "300"
[ -n "$(echo "$ESC" | jq_ "print(d.get('argumentsAgainst') or '')")" ] \
  && ok "the page carries the case against itself" || bad "no argumentsAgainst on the escalation"

curl -s -X POST "$G/demo/observe?scenario=lightheaded_on_standing&patientId=$PID" >/dev/null
for i in $(seq 1 24); do sleep 5
  A=$(curl -s "$G/patient/$PID/audit?limit=80")
  echo "$A" | grep -q "stood down" && break
done
echo "$A" | grep -q "stood down" \
  && ok "the restraint case: Escalator declined to page" \
  || bad "the Escalator never stood down — the counter-beat is missing"

# ------------------------------------------------ 5. human resolution -----
hd "human-terminated tasks"
TID=$(curl -s "$G/patient/$PID/exceptions" | jq_ "
x=[y for y in d['exceptions'] if y['kind']=='refused']
print(x[0]['taskId'] if x else '')")
OPT=$(curl -s "$G/patient/$PID/exceptions" | jq_ "
x=[y for y in d['exceptions'] if y['kind']=='refused']
print(x[0]['options'][0] if x else '')")
if [ -n "$TID" ]; then
  R=$(python3 -c "
import json,urllib.request
b=json.dumps({'actor':'Dr. Chen','option':'''$OPT'''}).encode()
r=urllib.request.Request('$G/patient/$PID/task/$TID/decide',data=b,headers={'Content-Type':'application/json'})
print(urllib.request.urlopen(r).read().decode())")
  has "a named human decided the refusal" "$R" "Dr. Chen"
  R2=$(python3 -c "
import json,urllib.request
b=json.dumps({'actor':'Dr. Patel','option':'''$OPT'''}).encode()
r=urllib.request.Request('$G/patient/$PID/task/$TID/decide',data=b,headers={'Content-Type':'application/json'})
print(urllib.request.urlopen(r).read().decode())")
  has "deciding twice keeps the first decision" "$R2" "alreadyDecidedBy"
else
  bad "no open refusal to decide"
fi

# ------------------------------------------------------- 6. the drill -----
hd "beat 2:00 — the Failure Drill (3 consecutive runs)"
for run in 1 2 3; do
  curl -s --max-time 30 -X POST "$G/chaos/arm?agent=scheduler&patientId=$PID&step=fhir_appointment" >/dev/null
  T=$(curl -s --max-time 30 -X POST "$G/demo/dispatch" -H 'Content-Type: application/json' \
      -d "{\"patientId\":\"$PID\",\"agent\":\"scheduler\",\"instructionId\":\"i_07\",\"payload\":{\"specialty\":\"cardiology\",\"daysOut\":7}}" \
      | jq_ "print(d['taskId'])")
  for i in $(seq 1 30); do sleep 5
    ST=$(curl -s "$G/patient/$PID/tasks" | jq_ "
t=[x for x in d['tasks'] if x.get('taskId')=='$T']
print(t[0]['status'] if t else 'pending')")
    [ "$ST" = "done" ] && break
  done
  RES=$(curl -s "$G/patient/$PID/tasks" | jq_ "
t=[x for x in d['tasks'] if x.get('taskId')=='$T'][0]
refs=[s.get('externalRef') for s in t.get('steps',[]) if s.get('externalRef')]
print(f\"{t['status']}|{t.get('attempt')}|{len(refs)}|{len(set(refs))}\")")
  IFS='|' read -r st att n uniq <<< "$RES"
  if [ "$st" = "done" ] && [ "${att:-0}" -ge 2 ] && [ "$n" = "$uniq" ]; then
    ok "run $run — killed mid-step, recovered on attempt $att, $n booking (no duplicate)"
  else
    bad "run $run — status=$st attempt=$att refs=$n unique=$uniq"
  fi
done
CAL=$(curl -s "$G/patient/$PID/tasks" | jq_ "
t=[x for x in d['tasks'] if x.get('taskId')=='$T'][0]
c=[s for s in t.get('steps',[]) if s['name']=='calendar_event']
r=(c[0].get('result') or {}) if c else {}
print('real' if r.get('htmlLink') else ('sim' if r.get('simulated') else 'missing'))")
eq "the booking also landed in a real Google Calendar" "$CAL" "real"

A=$(curl -s "$G/patient/$PID/audit?limit=200")
echo "$A" | grep -q "AGENT_DOWN" && ok "the kill is in the audit trail" || bad "no AGENT_DOWN recorded"
echo "$A" | grep -q "skipped on replay" && ok "completed steps were skipped, not repeated" || bad "no skip recorded"
W1=$(echo "$A" | python3 -c "
import sys,json,re
ws={re.search(r'leased by (\S+)',x['detail']).group(1)
    for x in json.load(sys.stdin)['audit'] if 'leased by' in x['detail']}
print(len(ws))")
python3 -c "import sys;sys.exit(0 if int('$W1')>=2 else 1)" \
  && ok "more than one distinct worker id ($W1) — a real process died" \
  || bad "only $W1 worker id — the kill may not have landed"

# --------------------------------------------------- 6b. the split fleet ---
hd "the decoupling, demonstrated"
REG=$(curl -s --max-time 20 "$G/registry")
SVC=$(echo "$REG" | jq_ "
a=[x for x in d['agents'] if x['displayName']=='Scheduler'][0]
print(a.get('service',''))")
case "$SVC" in
  https://vitahome-scheduler*) ok "Scheduler runs on its own Cloud Run service" ;;
  *) bad "Scheduler service field is '$SVC' — the split is not visible" ;;
esac
echo "$REG" | jq_ "
others=[x for x in d['agents'] if x['displayName']!='Scheduler']
print('OK' if all(x.get('service')=='gateway' for x in others) else 'NO')" \
  | grep -q OK && ok "the other six still on the gateway — the split was one routing change" \
  || bad "unexpected service map for the other agents"

# ------------------------------------------------------ 7. compliance -----
hd "compliance"
SC=$(curl -s --max-time 150 -X POST "$G/compliance/scan" -H 'Content-Type: application/json' -d '{
 "lines":["agent=scheduler pid=p_hero task=t_ab12 attempt=2",
          "Patient: Robert Hayes, 60M MRN 88213 admitted with chest pain",
          "leased by nj4-f7210a"]}')
eq "Gemma flagged the planted PHI" "$(echo "$SC" | jq_ "print(d['clean'])")" "False"
echo "$SC" | jq_ "
lines=' '.join(f['line'] for f in d['findings'])
print('OK' if 'Robert Hayes' in lines and 'p_hero' not in lines else 'NO')" \
  | grep -q OK && ok "opaque identifiers were NOT flagged (no false positives)" \
  || bad "the auditor flagged pseudonymous references"

# ------------------------------------------------------- 8. adversarial ---
hd "adversarial intake — a non-medical document"
NM=$(curl -s --max-time 120 -X POST "$G/capture" -H 'Content-Type: application/json' \
  -d '{"patientId":"p_adversarial","documentText":"TONY'\''S PIZZA\n1. Margherita 12.00\n2. Pepperoni 14.50\n3. Garlic bread 5.00\nOpen until 11pm. Call to order."}')
NI=$(echo "$NM" | jq_ "print(len(d['instructions']))")
info "documentType: $(echo "$NM" | jq_ "print(d['documentType'])")"
eq "no medical instructions invented from a menu" "$NI" "0"

# ---------------------------------------------------------- 9. surfaces ---
hd "web surfaces"
for p in / /capture /today /console /console/drill /console/fleets /architecture; do
  C=$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "$W$p")
  [ "$C" = "200" ] && ok "$p" || bad "$p returned $C"
done

# ------------------------------------------------------------ 10. storm ---
if [ "$STORM" = "1" ]; then
  hd "beat 3:20 — 200 fleets, real work"
  curl -s --max-time 300 -X POST "$G/demo/cohort?count=200" | jq_ "print(f\"    seeded {d['seeded']}, failed {d['failedCount']}\")"
  curl -s --max-time 200 -X POST "$G/demo/storm?count=200" >/dev/null &
  SLOW=0
  for i in $(seq 1 10); do
    sleep 12
    T=$(curl -s -o /dev/null -w '%{time_total}' --max-time 15 "$G/console/fleets?limit=250")
    python3 -c "import sys;sys.exit(0 if float('$T' or 99)<3 else 1)" || SLOW=$((SLOW+1))
  done
  [ "$SLOW" -eq 0 ] && ok "console stayed responsive throughout the burst" \
                    || bad "console was slow on $SLOW/10 samples during the burst"
  F=$(curl -s "$G/console/fleets?limit=250")
  info "$(echo "$F" | jq_ "print(f\"{d['count']} fleets · {d['active']} active · {d['needingHuman']} need a human\")")"
  # Scope to the COHORT. p_hero legitimately holds the open escalation and the
  # amlodipine refusal from the beats above — that is the correct end state for
  # it, not a failure. Cohort fleets only ever ran Scheduler tasks, so any of
  # them sitting in the queue would mean successful work was dead-lettered.
  echo "$F" | jq_ "
stuck=[f['id'] for f in d['fleets'] if f['cohort'] and f['state']=='needs_human']
print('OK' if not stuck else 'NO:'+','.join(stuck[:5]))" | grep -q OK \
    && ok "no cohort fleet dead-lettered a successful task" \
    || bad "cohort fleets landed in the exception queue — false dead-letters"
fi

# ------------------------------------------------------------- usage -----
hd "what this run cost"
curl -s "$G/usage" | python3 -c "
import sys,json;d=json.load(sys.stdin)
for m,v in d['byModel'].items():
    print(f\"    {m:<26} {v['calls']:>3} calls  {v['inputTokens']:>6} in  {v['outputTokens']:>6} out\")
t=d['totals']; print(f\"    {'TOTAL':<26} {t['calls']:>3} calls  {t['inputTokens']:>6} in  {t['outputTokens']:>6} out\")"

# ------------------------------------------------------------ verdict ----
printf "\n\033[1m▸ result\033[0m\n"
if [ "$FAIL" -eq 0 ]; then
  printf "  \033[32m%s checks passed — the system does what the demo claims\033[0m\n\n" "$PASS"
else
  printf "  \033[31m%s FAILED, %s passed\033[0m\n\n" "$FAIL" "$PASS"
  exit 1
fi
