import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const siteRoot = resolve(here, "../site");
const configOutput = resolve(siteRoot, "assets/runtime-config.js");
const redirectsOutput = resolve(siteRoot, "_redirects");
const context = (process.env.CONTEXT || process.env.HAJIRIFLOW_ENVIRONMENT || "development").trim();
const upstreamValue = (process.env.HAJIRIFLOW_API_BASE_URL || "").trim().replace(/\/+$/, "");

function normalizeUpstream(value) {
  if (!value) return "";
  let url;
  try {
    url = new URL(value);
  } catch {
    throw new Error("HAJIRIFLOW_API_BASE_URL must be an absolute http(s) URL.");
  }
  if (!['http:', 'https:'].includes(url.protocol)) {
    throw new Error("HAJIRIFLOW_API_BASE_URL must use http or https.");
  }
  if (url.username || url.password || url.search || url.hash) {
    throw new Error("HAJIRIFLOW_API_BASE_URL must not contain credentials, a query, or a fragment.");
  }
  if (context === "production" && url.protocol !== "https:") {
    throw new Error("Production HAJIRIFLOW_API_BASE_URL must use HTTPS.");
  }
  return url.href.replace(/\/+$/, "");
}

const upstream = normalizeUpstream(upstreamValue);
if (context === "production" && !upstream) {
  throw new Error("Production builds require HAJIRIFLOW_API_BASE_URL.");
}

const config = Object.freeze({ apiBasePath: "/api" });
mkdirSync(dirname(configOutput), { recursive: true });
writeFileSync(
  configOutput,
  `window.__HAJIRIFLOW_CONFIG__ = Object.freeze(${JSON.stringify(config)});\n`,
  "utf8",
);

const redirectRules = upstream
  ? `/api/* ${upstream}/api/:splat 200\n/* /index.html 200\n`
  : `/* /index.html 200\n`;
writeFileSync(redirectsOutput, redirectRules, "utf8");

console.log(`Generated browser runtime configuration for ${context}.`);
console.log(upstream ? "Configured same-origin /api proxy." : "No API proxy configured outside production.");
