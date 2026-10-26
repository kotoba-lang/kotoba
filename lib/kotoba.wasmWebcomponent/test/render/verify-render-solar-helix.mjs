// Real-pixel CI verification of examples/solar-helix's actual WebGPU draw
// path -- the gap ADR-2607078000 Addendum 7 explicitly left open. The pure
// mat4/vec3/sphere-mesh helpers have unit coverage (test/verify-solar-render-host.mjs),
// but the two real bugs Addendum 6 documents (a missing cos/sin host-import
// causing a LinkError, and a shared-uniform-buffer aliasing bug where every
// body's draw call ended up referencing only the LAST body's writeBuffer
// call because queue.writeBuffer runs immediately while pass.drawIndexed
// only records until queue.submit()) were both only found by a human
// eyeballing a live-browser screenshot. This is a CI-runnable stand-in for
// that eyeball.
//
// The ADR-2607078000 follow-up (animation + heliocentric/galactic view
// toggle) added a SECOND scenario here: without it, this test could only
// ever confirm the flat heliocentric view still renders -- exactly the
// half of the follow-up's own real-browser verification that a sandboxed
// automation session could re-confirm reliably. The galactic-frame view
// (tilt + forward drift, the actual "it's a helix" headline feature) had
// only ever been eyeballed once, live, before this session's earlier
// investigation found the sandboxed browser-automation tool itself
// intermittently blanking the canvas under sustained animation (see
// README's "sustained-animation verification gap" section) -- this
// real-GPU-CI harness sidesteps that tool entirely and settles the
// question definitively for a single rendered frame in each view mode.
//
// Approach: golden-landmark pixel sampling, not blob detection. An earlier
// attempt at connected-component blob-counting on this exact scene found
// Venus visually overlaps the Sun's disk at this render's fixed t=45-day
// camera/orbital-phase, occasionally merging into one connected component
// depending on the anti-aliasing threshold -- a real ambiguity for blind
// blob-counting, not a bug in the render. Sampling known landmark
// coordinates sidesteps that: for each of the 9 bodies, this searches a
// small window around a hand-verified screen position for the pixel most
// different from the background, and checks its color against that body's
// *exact* expected peak-lit color.
//
// Why the expected colors are exact (not fuzzy estimates): `solar_render_host.cljs`'s
// WGSL fragment shader computes `lit = color.rgb * (0.35 + 0.65*ndotl)` --
// at a sphere's most directly-lit point (ndotl == 1), `lit == color` exactly,
// i.e. the raw `body-palette` RGB value (scaled to 0-255) this repo's own
// source already defines. Measuring the actual rendered output against a
// real screenshot confirmed this: the brightest pixel near each body's
// landmark matched its `body-palette` entry to within 1/255 across all 9
// bodies -- this isn't a guessed tolerance, it's what a correct render
// produces by construction. A real regression (wrong host color, a missing
// body reading as background, or the buffer-aliasing bug reproducing --
// which would make every body except one read as that one body's color)
// moves a landmark's color far past this test's tolerance, not by 1-2 units.
//
// Both scenarios use `?test_fixed_t=45&test_galactic=<0|1>` (see
// index.html's script and solar_render_host.cljs's
// setup-solar-render-host docstring) to pin now-days/the view toggle to
// an exact, reproducible configuration -- now that main() is animated
// (reads now-days from wall-clock time every call), the render is no
// longer deterministic from page-load timing alone the way the original
// fixed-t=45-in-the-guest-source version was.
//
// Run: `node test/render/verify-render-solar-helix.mjs`
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

// Background clear color (gpu_draw_frame's colorAttachments clearValue,
// solar_render_host.cljs) as 0-255 RGB.
const BACKGROUND_RGB = [8, 8, 13];

// expectedRgb (body-palette's :color, scaled to 0-255 -- the exact
// peak-lit/ndotl==1 shader output) is the same in both view modes; only
// screen position moves. landmark [x,y] is a hand-verified screen
// position (in the screenshot's own pixel space, INCLUDING the canvas's
// 1px CSS border) for t=45 days in that scenario's view mode --
// heliocentric landmarks measured directly from a real screenshot;
// galactic landmarks computed by projecting the guest's own Chicory-
// verified t=45 galactic-frame positions (see
// test/verify-solar-helix-guest.mjs) through solar_render_host.cljs's
// exported mat4LookAt/mat4Perspective/mat4Multiply -- same derivation,
// just done once by hand instead of re-deriving it in this file.
const SCENARIOS = [
  {
    label: 'heliocentric (test_galactic=0)',
    query: 'test_fixed_t=45&test_galactic=0',
    bodies: [
      { name: 'sun', expectedRgb: [255, 219, 51], landmark: [241, 181], searchRadius: 6 },
      { name: 'mercury', expectedRgb: [153, 153, 153], landmark: [225, 181], searchRadius: 5 },
      { name: 'venus', expectedRgb: [230, 217, 153], landmark: [250, 191], searchRadius: 5 },
      { name: 'earth', expectedRgb: [64, 128, 230], landmark: [260, 191], searchRadius: 5 },
      { name: 'mars', expectedRgb: [204, 89, 51], landmark: [270, 188], searchRadius: 5 },
      { name: 'jupiter', expectedRgb: [217, 166, 102], landmark: [299, 184], searchRadius: 6 },
      { name: 'saturn', expectedRgb: [230, 204, 140], landmark: [319, 183], searchRadius: 6 },
      { name: 'uranus', expectedRgb: [140, 217, 230], landmark: [352, 182], searchRadius: 5 },
      { name: 'neptune', expectedRgb: [51, 89, 217], landmark: [379, 182], searchRadius: 5 },
    ],
  },
  {
    label: 'galactic frame / helix view (test_galactic=1)',
    query: 'test_fixed_t=45&test_galactic=1',
    bodies: [
      { name: 'sun', expectedRgb: [255, 219, 51], landmark: [240, 130], searchRadius: 2 },
      { name: 'mercury', expectedRgb: [153, 153, 153], landmark: [229, 130], searchRadius: 2 },
      { name: 'venus', expectedRgb: [230, 217, 153], landmark: [245, 127], searchRadius: 2 },
      { name: 'earth', expectedRgb: [64, 128, 230], landmark: [253, 128], searchRadius: 2 },
      { name: 'mars', expectedRgb: [204, 89, 51], landmark: [261, 128], searchRadius: 2 },
      { name: 'jupiter', expectedRgb: [217, 166, 102], landmark: [281, 130], searchRadius: 3 },
      { name: 'saturn', expectedRgb: [230, 204, 140], landmark: [296, 130], searchRadius: 3 },
      { name: 'uranus', expectedRgb: [140, 217, 230], landmark: [319, 130], searchRadius: 3 },
      { name: 'neptune', expectedRgb: [51, 89, 217], landmark: [339, 130], searchRadius: 3 },
    ],
  },
];

// Per-landmark color tolerance. Real measured drift across a correct render
// was ~1 unit (8-bit rounding only); the closest any two body-palette colors
// get to each other is venus/saturn at ~18 apart (both pale tan) -- but this
// test never cross-classifies against the *other* 8 colors, only checks each
// landmark against its OWN expected color, so this can stay generous for
// GPU/driver variance without risking a false pass via cross-body confusion.
const COLOR_TOLERANCE = 45;
// A landmark reading this close to the plain background means "no body
// rendered here" -- checked before the color match for a clearer failure
// message on a missing/moved body.
const MIN_DISTANCE_FROM_BACKGROUND = 80;

function rgbDistance(a, b) {
  return Math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2);
}

/** Search a (2r+1)x(2r+1) window around (cx,cy) for the pixel most different
 * from the background -- the peak-lit point of whatever sphere is there, if
 * any. */
function findPeakPixel(img, cx, cy, r) {
  let best = null;
  let bestDist = -1;
  for (let y = cy - r; y <= cy + r; y++) {
    for (let x = cx - r; x <= cx + r; x++) {
      if (x < 0 || y < 0 || x >= img.width || y >= img.height) continue;
      const [pr, pg, pb] = getPixel(img, x, y);
      const d = rgbDistance([pr, pg, pb], BACKGROUND_RGB);
      if (d > bestDist) {
        bestDist = d;
        best = { x, y, rgb: [pr, pg, pb], distFromBackground: d };
      }
    }
  }
  return best;
}

async function runScenario(browser, baseUrl, scenario) {
  const context = await browser.newContext({ deviceScaleFactor: 1 });
  const page = await context.newPage();
  const pageErrors = [];
  page.on('pageerror', (e) => pageErrors.push(String(e)));

  const url = `${baseUrl}/examples/solar-helix/index.html?${scenario.query}`;
  const gpu = await checkWebGpuAvailable(page, url);
  if (!gpu.available) {
    const msg = `WebGPU unavailable in this headless browser: ${gpu.reason}`;
    if (process.env.WEBGPU_RENDER_TEST_SKIP_IF_UNAVAILABLE) {
      console.warn(`SKIP: ${msg} (WEBGPU_RENDER_TEST_SKIP_IF_UNAVAILABLE set)`);
      await context.close();
      return;
    }
    console.error(`FAIL: ${msg}`);
    console.error('See README\'s "Automated render verification" section: this test targets macos-latest CI runners (real GPU); Linux/SwiftShader was tested and found unreliable.');
    failed = true;
    await context.close();
    return;
  }

  const outText = await waitForOutText(page);
  check(outText.includes('main() -> 0'), `[${scenario.label}] guest main() reported success: "${outText}"`);
  check(pageErrors.length === 0, `[${scenario.label}] no uncaught page errors (got: ${JSON.stringify(pageErrors)})`);

  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));

  const canvasHandle = await page.$('#c');
  check(canvasHandle !== null, `[${scenario.label}] canvas#c exists in the DOM`);
  const pngBuffer = await canvasHandle.screenshot();
  const img = decodePNG(pngBuffer);

  const foundColors = [];
  for (const body of scenario.bodies) {
    const [lx, ly] = body.landmark;
    const peak = findPeakPixel(img, lx, ly, body.searchRadius);
    check(
      peak.distFromBackground >= MIN_DISTANCE_FROM_BACKGROUND,
      `[${scenario.label}] ${body.name}: something renders near (${lx},${ly}) -- ` +
        `peak pixel (${peak.x},${peak.y}) rgb(${peak.rgb.join(',')}) is ${peak.distFromBackground.toFixed(1)} from background rgb(${BACKGROUND_RGB.join(',')}) (need >= ${MIN_DISTANCE_FROM_BACKGROUND})`
    );
    const colorDist = rgbDistance(peak.rgb, body.expectedRgb);
    check(
      colorDist <= COLOR_TOLERANCE,
      `[${scenario.label}] ${body.name}: peak pixel rgb(${peak.rgb.join(',')}) matches expected rgb(${body.expectedRgb.join(',')}) ` +
        `within ${COLOR_TOLERANCE} (distance ${colorDist.toFixed(1)})`
    );
    foundColors.push(peak.rgb);
  }

  // All 9 bodies are visually distinct colors by construction
  // (body-palette) -- if every landmark converged on the SAME color
  // (exactly the failure mode Addendum 6's buffer-aliasing bug
  // produced: every draw referencing only the last write), each
  // individual color-match check above would already fail, but this
  // gives one direct, easy-to-read signal for that specific regression
  // class too.
  const uniqueColors = new Set(foundColors.map((c) => c.join(',')));
  check(
    uniqueColors.size >= 7,
    `[${scenario.label}] at least 7 of 9 bodies render visually distinct colors (got ${uniqueColors.size} distinct colors -- a low count here is the exact signature of the shared-uniform-buffer aliasing bug ADR-2607078000 Addendum 6 documents, where every draw call ended up reading only the last body's data)`
  );

  await context.close();
}

async function main() {
  const { baseUrl, close } = await startStaticServer(REPO_ROOT);
  try {
    await withHeadlessBrowser(async (browser) => {
      for (const scenario of SCENARIOS) {
        await runScenario(browser, baseUrl, scenario);
      }
    });
  } finally {
    await close();
  }

  if (failed) process.exit(1);
  console.log('OK: examples/solar-helix renders all 9 bodies at their expected screen positions with their expected colors, in BOTH heliocentric and galactic-frame view modes -- verified against real decoded pixel data, not just "main() returned 0"');
}

main().catch((e) => {
  console.error('FAIL: unexpected error:', e);
  process.exit(1);
});
