/** @type {import('next').NextConfig} */
// StrictMode off: double-mounted effects abort SSE streams in dev.
// API base is resolved at RUNTIME from the hostname (never baked at build time)
// — see lib/api.ts. Do not proxy SSE through Next rewrites; it buffers.
module.exports = {
  reactStrictMode: false,
  output: "standalone",
};
