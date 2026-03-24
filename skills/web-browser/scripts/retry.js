/**
 * Shared retry + Chrome-restart helper used by nav.js and eval.js.
 *
 * Usage:
 *   import { withRetry } from "./retry.js";
 *   await withRetry(async () => { ... }, { retries: 3 });
 *
 * On each failure it checks whether Chrome is reachable; if not it
 * calls start.js to revive it before the next attempt.
 */

import { execFileSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { readFileSync } from "node:fs";
import { homedir } from "node:os";

const __dirname = dirname(fileURLToPath(import.meta.url));
const START     = join(__dirname, "start.js");
const SESSION   = process.env["BROWSER_SESSION"] || "default";

function getPort() {
  try {
    const portFile = join(homedir(), ".cache/scraping", SESSION, ".port");
    return Number(readFileSync(portFile, "utf8").trim());
  } catch {
    return null;
  }
}

async function isChromeAlive() {
  const port = getPort();
  if (!port) return false;
  try {
    const res = await fetch(`http://localhost:${port}/json/version`,
      { signal: AbortSignal.timeout(2000) });
    return res.ok;
  } catch {
    return false;
  }
}

function restartChrome() {
  console.error("↻ Chrome unreachable — restarting...");
  try {
    execFileSync(process.execPath, [START], {
      env: { ...process.env, BROWSER_SESSION: SESSION },
      stdio: ["ignore", "inherit", "inherit"],
      timeout: 30_000,
    });
  } catch (e) {
    console.error("✗ Chrome restart failed:", e.message);
  }
}

/**
 * @param {() => Promise<T>} fn      - async work to attempt
 * @param {{ retries?: number }} opts
 * @returns {Promise<T>}
 */
export async function withRetry(fn, { retries = 3 } = {}) {
  let lastErr;
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      return await fn();
    } catch (e) {
      lastErr = e;
      if (attempt < retries) {
        console.error(`✗ Attempt ${attempt}/${retries} failed: ${e.message}`);
        // Only restart if Chrome itself is gone
        if (!(await isChromeAlive())) {
          restartChrome();
          // Give Chrome a moment to settle before reconnecting
          await new Promise(r => setTimeout(r, 2000));
        }
      }
    }
  }
  throw lastErr;
}
