// Real-pixel CI verification of examples/gpu-clear's actual WebGPU draw
// path -- the gap ADR-2607078000 Addendum 7 explicitly left open: the pure
// bit-unpacking logic (test/verify-gpu-clear-host.mjs) has unit coverage,
// but pipeline creation / render-pass encoding / `queue.submit` timing and
// the actual rendered pixels did not, and needed a human with
// claude-in-chrome to eyeball a screenshot each time.
//
// This drives a real headless Chromium (see test/render/lib/webgpu-harness.mjs
// for what was investigated to make that reliable), loads
// examples/gpu-clear/index.html, lets the compiled `.kotoba` guest
// (`demo_gpu_clear.kotoba`, `(gpu-clear -16776961)` = packed
// 0xFF0000FF/opaque red) drive the real `gpu_clear` host-import, screenshots
// the `<canvas>`, decodes the PNG, and asserts every interior pixel is
// actually opaque red -- not just "did main() return 0 without throwing".
//
// Run: `node test/render/verify-render-gpu-clear.mjs`
// Requires: `npm install` (pulls in the `playwright` devDependency) and
// `npx playwright install chromium` at least once.
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { startStaticServer, withHeadlessBrowser, checkWebGpuAvailable, waitForOutText } from './lib/webgpu-harness.mjs';
import { decodePNG, getPixel } from './lib/png-decode.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '..', '..');

let failed = false;
function check(cond, message) {
  if (!cond) {
    failed = true;
    console.error(`FAIL: ${message}`);
  } else {
    console.log(`OK: ${message}`);
  }
}

// Expected clear color: demo_gpu_clear.kotoba calls (gpu-clear -16776961),
// the signed-i32 bit pattern of 0xFF0000FF -- opaque red per gpu_clear_host.cljs's
// unpack-rgba8 (see test/verify-gpu-clear-host.mjs for that unit-level proof).
const EXPECTED_RGB = [255, 0, 0];
const CHANNEL_TOLERANCE = 4; // small slack for GPU/driver rounding, not a hand-wave: still 60x too tight to pass any other primary/secondary color

async function main() {
  const { baseUrl, close } = await startStaticServer(REPO_ROOT);
  try {
    await withHeadlessBrowser(async (browser) => {
      const page = await browser.newPage();
      const pageErrors = [];
      page.on('pageerror', (e) => pageErrors.push(String(e)));

      const url = `${baseUrl}/examples/gpu-clear/index.html`;
      const gpu = await checkWebGpuAvailable(page, url);
      if (!gpu.available) {
        const msg = `WebGPU unavailable in this headless browser: ${gpu.reason}`;
        if (process.env.WEBGPU_RENDER_TEST_SKIP_IF_UNAVAILABLE) {
          console.warn(`SKIP: ${msg} (WEBGPU_RENDER_TEST_SKIP_IF_UNAVAILABLE set)`);
          return;
        }
        console.error(`FAIL: ${msg}`);
        console.error('See README\'s "Automated render verification" section: this test targets macos-latest CI runners (real GPU); Linux/SwiftShader was tested and found unreliable.');
        failed = true;
        return;
      }

      const outText = await waitForOutText(page);
      check(outText.includes('main() -> 0'), `guest main() reported success: "${outText}"`);
      check(pageErrors.length === 0, `no uncaught page errors (got: ${JSON.stringify(pageErrors)})`);

      // Give the compositor a couple of animation-frame ticks before
      // screenshotting -- WebGPU canvas presentation happens at "update the
      // rendering" time, not synchronously inside queue.submit().
      await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));

      const canvasHandle = await page.$('#c');
      check(canvasHandle !== null, 'canvas#c exists in the DOM');
      const pngBuffer = await canvasHandle.screenshot();
      const img = decodePNG(pngBuffer);

      // canvas.screenshot() on this element includes its 1px CSS border
      // (`style="border:1px solid #888"` in index.html) -- sample well
      // inside that margin.
      const margin = 6;
      let sampled = 0;
      let mismatches = 0;
      let firstMismatch = null;
      for (let y = margin; y < img.height - margin; y += 11) {
        for (let x = margin; x < img.width - margin; x += 11) {
          sampled += 1;
          const [r, g, b] = getPixel(img, x, y);
          const ok =
            Math.abs(r - EXPECTED_RGB[0]) <= CHANNEL_TOLERANCE &&
            Math.abs(g - EXPECTED_RGB[1]) <= CHANNEL_TOLERANCE &&
            Math.abs(b - EXPECTED_RGB[2]) <= CHANNEL_TOLERANCE;
          if (!ok) {
            mismatches += 1;
            if (!firstMismatch) firstMismatch = { x, y, r, g, b };
          }
        }
      }
      check(sampled > 50, `sampled a meaningful number of interior pixels (${sampled})`);
      check(
        mismatches === 0,
        mismatches === 0
          ? `all ${sampled} sampled interior pixels are opaque red (rgb within ${CHANNEL_TOLERANCE} of ${EXPECTED_RGB.join(',')})`
          : `${mismatches}/${sampled} sampled pixels were NOT opaque red -- first mismatch at (${firstMismatch.x},${firstMismatch.y}): rgb(${firstMismatch.r},${firstMismatch.g},${firstMismatch.b}), expected ~rgb(${EXPECTED_RGB.join(',')})`
      );
    });
  } finally {
    await close();
  }

  if (failed) process.exit(1);
  console.log('OK: examples/gpu-clear renders an actual opaque-red WebGPU canvas -- verified against real decoded pixel data, not just "main() returned 0"');
}

main().catch((e) => {
  console.error('FAIL: unexpected error:', e);
  process.exit(1);
});
