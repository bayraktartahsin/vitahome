# Stage addressing — why commands are not broadcast

A BroadcastChannel reaches every tab of the origin, and `StageLink` is mounted
in the root layout, so it is listening in every one of them.

That meant a single "click book" from the Director was performed once per open
tab. With the app open in two tabs, one command booked every appointment twice,
wrote two FHIR Appointments, and put two of each on the family's phone. It was
found on the real calendar as four appointments each appearing twice, and
reproduced exactly: one broadcast click, six scheduler tasks, six events.

The idempotency machinery could not help. Each duplicate was a genuinely
separate task with its own id, so each had its own iCalUID and each was a
correct, unique booking. The bug was upstream of idempotency: the command
itself was delivered twice.

## The contract

- The Director mints a nonce and opens the stage at `/capture?stage=<nonce>`.
- `StageLink` stores a nonce only if it arrived in that tab's own URL, in
  sessionStorage so it belongs to the tab and not the browser.
- Every command carries `to: <nonce>`. A tab acts only when `to` matches the
  nonce it holds.
- A tab with no nonce is a spectator. It answers a `hello` roll-call so the
  Director can show how many stages are listening, and does nothing else.

The roll-call is the safety net that matters most: the Director shows
"one stage connected" before GO, so two stages answering to the same nonce is
visible to the presenter rather than discovered afterwards on a phone.
