#!/usr/bin/env node

import { connect } from "./cdp.js";
import { withRetry } from "./retry.js";

const DEBUG = process.env.DEBUG === "1";
const log = DEBUG ? (...args) => console.error("[debug]", ...args) : () => {};

// Parse args: url [--new] [--retry N]
const args   = process.argv.slice(2);
const url    = args.find(a => !a.startsWith("--"));
const newTab = args.includes("--new");
const retryIdx = args.indexOf("--retry");
const retries  = retryIdx !== -1 ? Math.max(1, parseInt(args[retryIdx + 1]) || 3) : 1;

if (!url) {
  console.log("Usage: nav.js <url> [--new] [--retry N]");
  console.log("\nOptions:");
  console.log("  --new       Open in a new tab instead of the current one");
  console.log("  --retry N   Retry up to N times, restarting Chrome if needed (default: 1)");
  console.log("\nExamples:");
  console.log("  nav.js https://example.com             # Navigate current tab");
  console.log("  nav.js https://example.com --new       # Open in new tab");
  console.log("  nav.js https://example.com --retry 3   # Retry up to 3 times");
  process.exit(1);
}

// Global timeout scales with retry count (45s per attempt)
const globalTimeout = setTimeout(() => {
  console.error("✗ Global timeout exceeded");
  process.exit(1);
}, 45000 * retries);

try {
  await withRetry(async () => {
    log("connecting...");
    const cdp = await connect(5000);

    log("getting pages...");
    let targetId;

    if (newTab) {
      log("creating new tab...");
      const { targetId: newTargetId } = await cdp.send("Target.createTarget", {
        url: "about:blank",
      });
      targetId = newTargetId;
    } else {
      const pages = await cdp.getPages();
      const page = pages.at(-1);
      if (!page) {
        console.error("✗ No active tab found");
        process.exit(1);
      }
      targetId = page.targetId;
    }

    log("attaching to page...");
    const sessionId = await cdp.attachToPage(targetId);

    log("navigating...");
    await cdp.navigate(sessionId, url);

    console.log(newTab ? "✓ Opened:" : "✓ Navigated to:", url);

    log("closing...");
    cdp.close();
    log("done");
  }, { retries });
} catch (e) {
  console.error("✗", e.message);
  process.exit(1);
} finally {
  clearTimeout(globalTimeout);
  setTimeout(() => process.exit(0), 100);
}
