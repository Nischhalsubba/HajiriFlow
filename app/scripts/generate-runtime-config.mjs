import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const output = resolve(here, "../site/assets/runtime-config.js");
const context = (process.env.CONTEXT || process.env.HAJIRIFLOW_ENVIRONMENT || "development").trim();
const apiBaseUrl = (process.env.HAJIRIFLOW_API_BASE_URL || "").trim().replace(/\/+$/, "");
const csrfCookieName = (process.env.HAJIRIFLOW_CSRF_COOKIE_NAME || "hajiriflow_csrf").trim();

if (apiBaseUrl && !/^https?:\/\//i.test(apiBaseUrl)) {
  throw new Error("HAJIRIFLOW_API_BASE_URL must be an absolute http(s) URL.");
}

if (context === "production" && !apiBaseUrl) {
  throw new Error("Production builds require HAJIRIFLOW_API_BASE_URL.");
}

if (context === "production" && !/^https:\/\//i.test(apiBaseUrl)) {
  throw new Error("Production HAJIRIFLOW_API_BASE_URL must use HTTPS.");
}

if (!/^[A-Za-z0-9_-]{1,128}$/.test(csrfCookieName)) {
  throw new Error("HAJIRIFLOW_CSRF_COOKIE_NAME contains unsupported characters.");
}

const config = Object.freeze({
  apiBaseUrl,
  csrfCookieName,
});

mkdirSync(dirname(output), { recursive: true });
writeFileSync(
  output,
  `window.__HAJIRIFLOW_CONFIG__ = Object.freeze(${JSON.stringify(config)});\n`,
  "utf8",
);

console.log(`Generated ${output} for ${context}.`);
