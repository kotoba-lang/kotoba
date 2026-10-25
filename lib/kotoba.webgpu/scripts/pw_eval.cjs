// playwright-clj bridge (CommonJS). Resolve playwright via NODE_PATH; resolve the chromium
// binary via Playwright's own `chromium.executablePath()` (override with PW_EXE). Usage:
//   NODE_PATH=<pw>/node_modules node pw_eval.cjs <js-file> [url]
//
// Cross-platform note (fixed 2026-07-08): this used to hand-roll a cache-path search under
// `~/Library/Caches/ms-playwright` for a `chromium_headless_shell*/chrome-headless-shell-mac-arm64`
// binary -- both the cache root and the per-platform subdirectory name were macOS-only, so on
// Linux (e.g. ubuntu-latest CI runners, whose cache lives at `~/.cache/ms-playwright` and whose
// binary subdirectory is `chrome-headless-shell-linux64`) `findExe()` silently returned
// `undefined` and every launch fell through to Playwright's own default resolution instead.
// `chromium.executablePath()` is the public, version-independent Playwright API for exactly this
// (same technique that fixed the analogous macOS-only-binary-resolution issue in the sibling
// wasm-webcomponent repo's WebGPU harness) -- it resolves the correct platform/arch binary
// Playwright actually has installed, with no OS-specific path logic here at all.
const { chromium } = require('playwright');
const { readFileSync } = require('fs');
function findExe() {
  if (process.env.PW_EXE) return process.env.PW_EXE;
  try { return chromium.executablePath(); } catch (_e) { return undefined; }
}
(async () => {
  const js = readFileSync(process.argv[2], 'utf8');
  const url = process.argv[3] || 'about:blank';
  const browser = await chromium.launch({ headless: true, executablePath: findExe(),
    args: ['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist','--enable-webgl'] });
  try {
    const page = await browser.newPage();
    if (url !== 'about:blank') await page.goto(url, { waitUntil: 'domcontentloaded' });
    const result = await page.evaluate(`(async () => { ${js} })()`);
    console.log(JSON.stringify({ ok: true, result }));
  } catch (e) { console.log(JSON.stringify({ ok: false, error: String(e) })); }
  finally { await browser.close(); }
})();
