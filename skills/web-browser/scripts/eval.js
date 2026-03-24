#!/usr/bin/env node

import { connect } from "./cdp.js";
import { withRetry } from "./retry.js";

const DEBUG = process.env.DEBUG === "1";
const log = DEBUG ? (...args) => console.error("[debug]", ...args) : () => {};

// Parse args: strip --retry N before treating the rest as code
const rawArgs  = process.argv.slice(2);
const retryIdx = rawArgs.indexOf("--retry");
const retries  = retryIdx !== -1 ? Math.max(1, parseInt(rawArgs[retryIdx + 1]) || 3) : 1;
const codeArgs = retryIdx !== -1 ? rawArgs.toSpliced(retryIdx, 2) : rawArgs;
const code     = codeArgs.join(" ");

if (!code) {
  console.log("Usage: eval.js [--retry N] 'code'");
  console.log("\nOptions:");
  console.log("  --retry N   Retry up to N times, restarting Chrome if needed (default: 1)");
  console.log("\nExamples:");
  console.log('  eval.js "document.title"');
  console.log('  eval.js --retry 3 "document.title"');
  console.log("  eval.js \"document.querySelectorAll('a').length\"");
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
    const pages = await cdp.getPages();
    const page = pages.at(-1);

    if (!page) {
      console.error("✗ No active tab found");
      process.exit(1);
    }

    log("attaching to page...");
    const sessionId = await cdp.attachToPage(page.targetId);

    log("evaluating...");
    const expression = `(async () => { return (${code}); })()`;
    const result = await cdp.evaluate(sessionId, expression);

    log("formatting result...");
    if (Array.isArray(result)) {
      for (let i = 0; i < result.length; i++) {
        if (i > 0) console.log("");
        for (const [key, value] of Object.entries(result[i])) {
          console.log(`${key}: ${value}`);
        }
      }
    } else if (typeof result === "object" && result !== null) {
      for (const [key, value] of Object.entries(result)) {
        console.log(`${key}: ${value}`);
      }
    } else {
      console.log(result);
    }

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
