/**
 * API base resolved at RUNTIME from the hostname.
 *
 * Deliberately not NEXT_PUBLIC_* : that is inlined at build time, and Cloud Run's
 * --set-build-env-vars does not reach the Docker build, which silently ships a
 * localhost URL to production. Resolving at runtime removes the whole class of bug.
 *
 * Also: never proxy SSE through Next rewrites — the framework buffers the stream
 * and the browser receives nothing until it closes. Hit the gateway directly.
 */
export const API =
  typeof window !== "undefined" && window.location.hostname !== "localhost"
    ? "https://vitahome-gateway-205100594497.us-central1.run.app"
    : "http://localhost:8080";

export async function getJSON<T>(path: string): Promise<T> {
  const r = await fetch(`${API}${path}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return r.json() as Promise<T>;
}
