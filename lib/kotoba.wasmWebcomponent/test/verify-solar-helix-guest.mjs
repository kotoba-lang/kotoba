// Dependency-free numerical-soundness sweep for
// examples/solar-helix/demo_solar_helix.wasm's own computed positions --
// runs the REAL compiled guest (not solar_render_host.cljs's camera math)
// through Node's native WebAssembly with stub cos/sin/now-days/
// galactic-frame host-imports, across the full now-days wrap range (see
// solar_render_host.cljs's days-per-second/wrap-days), for BOTH view
// modes. Exists because the ADR-2607078000 follow-up (animation +
// galactic-frame toggle) investigation found the guest's own math was
// never the problem — every t/galactic-frame combination produces finite,
// bounded x/y/z — while the LIVE render intermittently went blank during
// sustained real-browser requestAnimationFrame runs in one sandboxed
// session (root-caused to that environment's own GPU/renderer flakiness
// under this tool's repeated device/canvas creation, not a code defect;
// see the ADR's addendum for the full investigation). This test makes the
// "the guest's math itself is sound" half of that finding permanent and
// automatically re-checked for any future change to the guest source,
// without needing a GPU. Run: `node test/verify-solar-helix-guest.mjs`
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));
const bytes = await readFile(path.join(here, '..', 'examples', 'solar-helix', 'demo_solar_helix.wasm'));

let failed = false;
function check(cond, message) {
  if (!cond) {
    failed = true;
    console.error(`FAIL: ${message}`);
  } else {
    console.log(`OK: ${message}`);
  }
}

// Same illustrative-scale reasoning as solar_render_host.cljs: orbit
// radii are sqrt-scaled to roughly [0, 1.5], so any position component
// beyond +-10 is unambiguously a bug (off-frustum drift, NaN-adjacent
// blowup), not legitimate scene content.
const SANE_BOUND = 10;

async function runOnce(tDays, galactic) {
  const positions = {};
  const importObject = {
    kotoba: {
      cos: (x) => Math.cos(x),
      sin: (x) => Math.sin(x),
      now_days: () => tDays,
      galactic_frame: () => (galactic ? 1 : 0),
      gpu_set_position: (id, x, y, z) => {
        positions[id] = [x, y, z];
        return 0;
      },
      gpu_draw_frame: () => 0,
    },
  };
  const { instance } = await WebAssembly.instantiate(bytes, importObject);
  const result = instance.exports.main();
  return { result, positions };
}

// Sweep the full wrap range (solar_render_host.cljs's wrap-days = 80) in
// fine steps, both view modes -- this is the sweep that originally caught
// nothing wrong with the guest, making that finding permanent.
const STEPS = 40;
let allFinite = true;
let allBounded = true;
let heliocentricYAlwaysZero = true;

for (let i = 0; i <= STEPS; i++) {
  const t = (80 * i) / STEPS;
  for (const galactic of [false, true]) {
    const { result, positions } = await runOnce(t, galactic);
    if (result !== 0) {
      failed = true;
      console.error(`FAIL: main() returned ${result} (expected 0) at t=${t} galactic=${galactic}`);
    }
    for (const [id, [x, y, z]] of Object.entries(positions)) {
      if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) {
        allFinite = false;
        console.error(`FAIL: non-finite position for body ${id} at t=${t} galactic=${galactic}: [${x},${y},${z}]`);
      }
      if (Math.abs(x) > SANE_BOUND || Math.abs(y) > SANE_BOUND || Math.abs(z) > SANE_BOUND) {
        allBounded = false;
        console.error(`FAIL: out-of-bound position for body ${id} at t=${t} galactic=${galactic}: [${x},${y},${z}]`);
      }
      if (!galactic && y !== 0) {
        heliocentricYAlwaysZero = false;
        console.error(`FAIL: heliocentric view (galactic=false) produced nonzero y for body ${id} at t=${t}: y=${y}`);
      }
    }
  }
}

check(allFinite, `every position component is finite across ${STEPS + 1} t-values x 2 view modes`);
check(allBounded, `every position component stays within +-${SANE_BOUND} world units (no off-frustum blowup)`);
check(heliocentricYAlwaysZero, 'heliocentric view (galactic=false) always keeps y=0 -- the flat-plane invariant the whole view-toggle design depends on');

// Spot-check the Sun (body 0) specifically: r=0 means its x/y are always
// 0 regardless of view, only its z (the forward-drift axis) should ever
// move, and only when galactic frame is on.
{
  const helio = await runOnce(40.0, false);
  const gal = await runOnce(40.0, true);
  check(helio.positions[0][0] === 0 && helio.positions[0][1] === 0 && helio.positions[0][2] === 0,
        'Sun stays at the origin in heliocentric view (r=0, no forward drift)');
  check(gal.positions[0][0] === 0 && gal.positions[0][1] === 0,
        "Sun's x/y stay 0 in galactic view too -- only z (forward drift) moves it");
  check(gal.positions[0][2] < 0,
        `Sun's galactic-view z is negative (drifting away from the camera at z=+2.7, not toward it) -- got ${gal.positions[0][2]}`);
}

if (failed) process.exit(1);
console.log('OK: demo_solar_helix.wasm produces finite, bounded, correctly-signed positions across the full now-days wrap range in both view modes');
