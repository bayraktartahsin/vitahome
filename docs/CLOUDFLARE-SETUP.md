# vitahome.vitamedas.com — Cloudflare setup (5 minutes, done once)

Design: the subdomain is answered entirely by Cloudflare and forwarded to the
Cloud Run app by a Worker. **No traffic ever touches the Hetzner server**, and
nothing outside the `vitahome` subdomain is involved. The run.app URLs keep
working forever as fallbacks.

## Step 1 — Fix the DNS record (the panel you already have open)

DNS → Records → row `vitahome` → Edit:

- **IPv4 address:** `192.0.2.1`
  (a reserved, non-routable placeholder — guarantees nothing can reach Hetzner
  through this name, even if the Worker is ever removed)
- **Proxy status:** toggle ON → orange **Proxied**
- **Save**

Touch no other row.

## Step 2 — Create the Worker

1. Cloudflare sidebar → **Compute (Workers)** → **Create** →
   **Start with Hello World** → name it `vitahome-proxy` → **Deploy**.
2. Click **Edit code**, select everything in the editor (Cmd-A), delete it,
   paste this, then **Deploy**:

```js
// vitahome-proxy — forwards vitahome.vitamedas.com to the Cloud Run app.
// Scoped by its route to this one subdomain; touches nothing else.
const ORIGIN = "vitahome-web-205100594497.us-central1.run.app";

export default {
  async fetch(request) {
    const url = new URL(request.url);
    url.hostname = ORIGIN;
    url.port = "";
    return fetch(new Request(url, request));
  },
};
```

## Step 3 — Point the subdomain at the Worker

On the `vitahome-proxy` worker page → **Settings** → **Domains & Routes** →
**+ Add** → **Route**:

- Zone: `vitamedas.com`
- Route: `vitahome.vitamedas.com/*`
- Save.

(A route matches ONLY that hostname — api.vitamedas.com, admin, the root site
and everything else are untouched by definition.)

## Step 4 — Tell Claude "done"

Claude verifies every page end to end, and only then updates the Devpost links,
the Director, and the docs — with the run.app URLs kept as fallbacks.

## Rollback (if ever wanted)

Delete the Worker route. The subdomain then serves nothing (placeholder IP),
and every published run.app link still works. Nothing else changes.
