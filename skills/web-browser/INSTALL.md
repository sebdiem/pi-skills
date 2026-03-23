# Web Browser Skill — Sprite Installation

## Problem

Sprite environments ship with `/usr/bin/chromium-browser`, but it's a snap wrapper that doesn't work (no snapd running in the container). The skill's `start.js` finds this broken wrapper before `CHROME_BIN` and fails silently.

## Steps

### 1. Install system libraries

Chrome needs a handful of shared libraries that aren't in the base image:

```bash
sudo apt-get update
sudo apt-get install -y libnss3 libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 \
  libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
  libpango-1.0-0 libcairo2 libasound2t64 libxshmfence1 libxfixes3 \
  fonts-liberation xdg-utils
```

### 2. Download Chrome

Use Puppeteer's browser installer to fetch a real Chrome binary:

```bash
npx @puppeteer/browsers install chrome@stable --path ~/.chrome
```

This downloads to `~/.chrome/chrome/linux-<version>/chrome-linux64/chrome`.

### 3. Create a stable symlink

```bash
ln -sf ~/.chrome/chrome/linux-*/chrome-linux64/chrome ~/.chrome/chrome-bin
```

### 4. Replace the broken snap wrapper

The snap wrapper at `/usr/bin/chromium-browser` is executable, so `start.js` picks it up before checking `CHROME_BIN`. Replace it:

```bash
sudo mv /usr/bin/chromium-browser /usr/bin/chromium-browser.snap-wrapper
sudo ln -sf ~/.chrome/chrome-bin /usr/bin/chromium-browser
```

### 5. Set CHROME_BIN

```bash
echo 'export CHROME_BIN="$HOME/.chrome/chrome-bin"' >> ~/.bashrc
export CHROME_BIN="$HOME/.chrome/chrome-bin"
```

### 6. Install npm dependencies

```bash
cd ~/.pi/agent/skills/web-browser/scripts && npm install
```

### 7. Verify

```bash
chromium-browser --version          # should print "Google Chrome for Testing ..."

export BROWSER_SESSION="install-test"
cd ~/.pi/agent/skills/web-browser/scripts
node start.js                       # ✓ Chrome started on :XXXXX
node nav.js https://example.com     # ✓ Navigated to: https://example.com
node eval.js 'document.title'       # Example Domain
node screenshot.js                  # /tmp/screenshot-....png
```

## Notes

- Chrome runs **headless** automatically (no `DISPLAY` in the container).
- The dbus errors in Chrome's stderr are harmless — there's no system bus in the container.
- Each `BROWSER_SESSION` gets its own Chrome instance, port, and log directory.
