// playwright-clj bridge (CommonJS). Resolve playwright via NODE_PATH; auto-detect a headless
// chromium shell from the ms-playwright cache (override with PW_EXE). Usage:
//   NODE_PATH=<pw>/node_modules node pw_eval.cjs <js-file> [url]
const { chromium } = require('playwright');
const { readFileSync, readdirSync, existsSync } = require('fs');
const os = require('os'), path = require('path');
function findExe() {
  if (process.env.PW_EXE) return process.env.PW_EXE;
  const cache = path.join(os.homedir(), 'Library/Caches/ms-playwright');
  if (!existsSync(cache)) return undefined;
  const dirs = readdirSync(cache).filter(d => d.startsWith('chromium_headless_shell')).sort();
  for (const d of dirs.reverse()) {
    const exe = path.join(cache, d, 'chrome-headless-shell-mac-arm64', 'chrome-headless-shell');
    if (existsSync(exe)) return exe;
  }
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
