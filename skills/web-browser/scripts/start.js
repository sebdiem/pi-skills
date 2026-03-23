#!/usr/bin/env node

import { spawn, execSync } from "node:child_process";
import { createServer } from "node:net";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { writeFileSync } from "node:fs";

const SESSION = process.env["BROWSER_SESSION"] || "default";
const SCRAPING_ROOT = join(process.env["HOME"], ".cache/scraping");
const SCRAPING_DIR = join(SCRAPING_ROOT, SESSION);
const PORT_FILE = join(SCRAPING_DIR, ".port");

const useProfile = process.argv[2] === "--profile";

if (process.argv[2] && process.argv[2] !== "--profile") {
  console.log("Usage: start.ts [--profile]");
  console.log("\nOptions:");
  console.log(
    "  --profile  Copy your default Chrome profile (cookies, logins)",
  );
  console.log("\nExamples:");
  console.log("  start.ts            # Start with fresh profile");
  console.log("  start.ts --profile  # Start with your Chrome profile");
  process.exit(1);
}

// Kill only this session's Chrome instance (leave other sessions and user's Chrome alone)
try {
  execSync(`pkill -f -- 'user-data-dir=.*\\.cache/scraping/${SESSION}'`, { stdio: "ignore" });
} catch {}

// Wait a bit for processes to fully die
await new Promise((r) => setTimeout(r, 1000));

// Setup profile directory and clean stale Chrome locks
// (leftover locks prevent a second Chrome instance from starting)
execSync(`mkdir -p "${SCRAPING_DIR}"`, { stdio: "ignore" });
for (const lock of ["SingletonLock", "SingletonSocket", "SingletonCookie"]) {
  try { execSync(`rm -f "${join(SCRAPING_DIR, lock)}"`, { stdio: "ignore" }); } catch {}
}

if (useProfile) {
  // Sync profile with rsync (much faster on subsequent runs)
  execSync(
    `rsync -a --delete "${process.env["HOME"]}/.config/google-chrome/" "${SCRAPING_DIR}/"`,
    { stdio: "pipe" },
  );
}

// Find a free port
function getFreePort() {
  return new Promise((resolve, reject) => {
    const srv = createServer();
    srv.listen(0, "127.0.0.1", () => {
      const port = srv.address().port;
      srv.close(() => resolve(port));
    });
    srv.on("error", reject);
  });
}

const port = await getFreePort();

// Save port so other scripts can find it
writeFileSync(PORT_FILE, String(port));

// Find Chrome/Chromium binary
function findChrome() {
  const candidates = [
    "/usr/bin/google-chrome-stable",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium-browser",
    "/usr/bin/chromium",
    process.env["CHROME_BIN"],
  ].filter(Boolean);

  for (const bin of candidates) {
    try {
      execSync(`test -x "${bin}"`, { stdio: "ignore" });
      return bin;
    } catch {}
  }
  throw new Error("Could not find Chrome/Chromium. Install chromium-browser or set CHROME_BIN.");
}

const chromeBin = findChrome();

// Check if we have a display (if not, use headless mode)
const hasDisplay = process.env["DISPLAY"] || process.env["WAYLAND_DISPLAY"];
const headlessArgs = hasDisplay ? [] : ["--headless=new", "--no-sandbox", "--disable-gpu"];

// Start Chrome in background (detached so Node can exit)
spawn(
  chromeBin,
  [
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${SCRAPING_DIR}`,
    "--profile-directory=Default",
    "--disable-search-engine-choice-screen",
    "--no-first-run",
    "--disable-features=ProfilePicker",
    ...headlessArgs,
  ],
  { detached: true, stdio: "ignore" },
).unref();

// Wait for Chrome to be ready by checking the debugging endpoint
let connected = false;
for (let i = 0; i < 30; i++) {
  try {
    const response = await fetch(`http://localhost:${port}/json/version`);
    if (response.ok) {
      connected = true;
      break;
    }
  } catch {
    await new Promise((r) => setTimeout(r, 500));
  }
}

if (!connected) {
  console.error("✗ Failed to connect to Chrome");
  process.exit(1);
}

// Start background watcher for logs/network (detached)
const scriptDir = dirname(fileURLToPath(import.meta.url));
const watcherPath = join(scriptDir, "watch.js");
spawn(process.execPath, [watcherPath], {
  detached: true,
  stdio: "ignore",
  env: { ...process.env, BROWSER_SESSION: SESSION },
}).unref();

console.log(
  `✓ Chrome started on :${port} [session=${SESSION}]${useProfile ? " with your profile" : ""}`,
);
