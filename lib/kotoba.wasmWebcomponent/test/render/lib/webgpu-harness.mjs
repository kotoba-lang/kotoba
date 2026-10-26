// Shared harness for real-pixel WebGPU render verification (see README's
// "Automated render verification" section for the full writeup of what was
// investigated and why this shape).
//
// Key finding this harness bakes in: Playwright's *default* headless launch
// silently resolves to the stripped-down "headless shell" Chromium variant
// on at least one platform this was tested on, which has no `navigator.gpu`
// at all -- WebGPU needs the full Chromium/"Chrome for Testing" binary.
// `chromium.executablePath()` (a public Playwright API, not a hardcoded
// version-pinned cache path) reliably returns that full-binary path
// regardless of the `headless` option, so every launch here goes through it
// explicitly instead of relying on `chromium.launch()`'s own default
// resolution.
//
// Second finding: `navigator.gpu` is only populated on a real http(s)
// origin, not on a fresh `about:blank` page -- always navigate before
// checking/using it.
//
// Third finding (the actual scope decision this harness encodes): this was
// verified to work reliably on macOS (real Metal-backed GPU process, no
// special launch flags needed). The same check against Linux/SwiftShader
// software rendering (via `xvfb-run` + `--enable-unsafe-webgpu
// --use-angle=swiftshader`) produced `Instance dropped in popErrorScope`
// errors and blank canvases -- unreliable, not wired into CI. See the
// README for the full evidence. Callers on an unsupported platform should
// expect `checkWebGpuAvailable` to report `available: false` and should
// skip (not fail red) rather than force it.
import { chromium } from 'playwright';
import http from 'node:http';
import { readFile } from 'node:fs/promises';
import path from 'node:path';

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript',
  '.mjs': 'text/javascript',
  '.cjs': 'text/javascript',
  '.wasm': 'application/wasm',
  '.json': 'application/json',
  '.kotoba': 'text/plain',
  '.edn': 'text/plain',
};

/** Serve `rootDir` over plain HTTP on an OS-assigned localhost port (no
 * external dependency -- Node's own `http` module). Resolves to
 * `{ baseUrl, close }`. */
export function startStaticServer(rootDir) {
  return new Promise((resolve, reject) => {
    const server = http.createServer(async (req, res) => {
      try {
        const urlPath = decodeURIComponent(req.url.split('?')[0]);
        const filePath = path.join(rootDir, urlPath);
        if (!filePath.startsWith(rootDir)) {
          res.writeHead(403);
          res.end('forbidden');
          return;
        }
        const data = await readFile(filePath);
        const ext = path.extname(filePath);
        res.writeHead(200, { 'Content-Type': MIME_TYPES[ext] || 'application/octet-stream' });
        res.end(data);
      } catch (e) {
        res.writeHead(404);
        res.end('not found: ' + String(e && e.message));
      }
    });
    server.on('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address();
      resolve({
        baseUrl: `http://127.0.0.1:${port}`,
        close: () => new Promise((r) => server.close(r)),
      });
    });
  });
}

/** Launch the full (non-headless-shell) Chromium build headless, run `fn(page)`,
 * always close the browser afterward. */
export async function withHeadlessBrowser(fn) {
  const executablePath = chromium.executablePath();
  const browser = await chromium.launch({ headless: true, executablePath });
  try {
    return await fn(browser);
  } finally {
    await browser.close();
  }
}

/** Navigate to `url` and report whether a real WebGPU device is obtainable.
 * Never throws -- returns `{ available: false, reason }` on any failure so
 * callers can skip cleanly instead of crashing. */
export async function checkWebGpuAvailable(page, url) {
  await page.goto(url, { waitUntil: 'load' });
  return page.evaluate(async () => {
    if (!navigator.gpu) return { available: false, reason: 'navigator.gpu is undefined' };
    try {
      const adapter = await navigator.gpu.requestAdapter();
      if (!adapter) return { available: false, reason: 'navigator.gpu.requestAdapter() returned null' };
      const device = await adapter.requestDevice();
      return { available: !!device, reason: device ? undefined : 'adapter.requestDevice() returned null' };
    } catch (e) {
      return { available: false, reason: String(e) };
    }
  });
}

/** Wait for `#out`'s textContent to stop reading "loading...", then return it. */
export async function waitForOutText(page, timeout = 20000) {
  await page.waitForFunction(
    () => {
      const el = document.getElementById('out');
      return el && el.textContent && !el.textContent.includes('loading');
    },
    { timeout }
  );
  return page.evaluate(() => document.getElementById('out').textContent);
}
