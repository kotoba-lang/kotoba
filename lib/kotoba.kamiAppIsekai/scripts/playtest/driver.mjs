#!/usr/bin/env node
// scripts/playtest/driver.mjs — スライムハント (Slime Hunt) Playwright playtest driver.
//
// The first time this ecosystem's playtest-via-Playwright work becomes a committed,
// reusable script instead of one-off inline code (this session repeatedly play-tested
// this same game via never-committed scripts dispatching real keyboard events, reading
// the window.__slimeHunt* debug hooks, and taking screenshots — see dev/slime_hunt/game.cljk
// for those hooks). Boots a local static server serving the built game (game.html +
// dev/out/game.js + public/games/slime-hunt/{scene.edn,logic.cljc}), drives it with REAL
// keyboard events (not scripted timings — a closed-loop controller polling
// window.__slimeHuntSnapshot()/__slimeHuntGlobals() every tick, matching this game's own
// fixed arena layout in public/games/slime-hunt/logic.cljk: player spawns at [0,0], 8 orbs
// on an r=450 ring, 3 slimes on an r=700 ring), and saves real PNG screenshots at the 5
// moments the task calls out: title, just-after-a-pickup, just-after-a-hit, victory,
// game-over.
//
// Two episodes (both needed to hit all 5 moments without contaminating the "clean" runs
// with unintended damage/pickups):
//   victory — collect all 8 orbs, avoiding the 3 slimes, until the :victory flow fires.
//   lose    — deliberately walk into slimes until 3 hits drain all lives and :gameover fires.
//
// Usage:
//   node scripts/playtest/driver.mjs [--out-dir DIR] [--port N] [--headed] [--scene PATH]
//
// Prints a single JSON summary line to stdout on success: {ok, outDir, shots:[{name,path}…],
// victory:{…}, lose:{…}}. Non-zero exit + {ok:false,error} JSON on failure.
//
// Env overrides:
//   PLAYWRIGHT_NODE_MODULES — dir containing an installed `playwright` (default: resolve
//     the sibling kotoba-lang/webgpu checkout's node_modules — this repo has none of its
//     own, see README "Zero-dep" — reusing webgpu's already-installed playwright + cached
//     chromium binary instead of installing a redundant copy).
//   PW_EXE — force a specific chromium binary path (skips chromium.executablePath()).

import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const require_ = createRequire(import.meta.url);
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '..', '..'); // scripts/playtest/driver.mjs -> repo root

// ---- CLI args --------------------------------------------------------------------------
function parseArgs(argv) {
  const out = { outDir: null, port: 0, headed: false, scenePath: null, maxTotalMs: 120000 };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--out-dir') out.outDir = argv[++i];
    else if (a === '--port') out.port = Number(argv[++i]);
    else if (a === '--headed') out.headed = true;
    else if (a === '--scene') out.scenePath = argv[++i];
    else if (a === '--max-total-ms') out.maxTotalMs = Number(argv[++i]);
  }
  return out;
}
const args = parseArgs(process.argv.slice(2));
const OUT_DIR = path.resolve(args.outDir || path.join(REPO_ROOT, 'dev', 'out', 'playtest-screenshots'));

// ---- resolve the `playwright` package ---------------------------------------------------
// kami-app-isekai has no node_modules of its own (zero-dep .cljc repo) — reuse the sibling
// kotoba-lang/webgpu checkout's already-installed playwright + cached chromium binary (the
// SAME instance kami.playwright/scripts/pw_eval.cjs uses for this repo's own render-test),
// rather than installing a redundant copy. Override with PLAYWRIGHT_NODE_MODULES=<dir> if
// the sibling isn't at the conventional ../webgpu path (e.g. an isolated agent worktree).
function resolvePlaywright() {
  const candidates = [
    process.env.PLAYWRIGHT_NODE_MODULES,
    path.join(REPO_ROOT, '..', 'webgpu', 'node_modules'),
    path.join(REPO_ROOT, 'node_modules'),
  ].filter(Boolean);
  const tried = [];
  for (const dir of candidates) {
    try {
      return require_(path.join(dir, 'playwright'));
    } catch (e) {
      tried.push(`${dir}: ${e.message}`);
    }
  }
  try {
    return require_('playwright'); // last resort: bare specifier (global/NODE_PATH resolution)
  } catch (e) {
    throw new Error(
      `could not resolve the "playwright" package. Tried:\n${tried.join('\n')}\nand bare 'playwright': ${e.message}\n` +
      `Set PLAYWRIGHT_NODE_MODULES=<dir-containing-node_modules/playwright> to override.`
    );
  }
}
const { chromium } = resolvePlaywright();

// ---- resolve the chromium binary ---------------------------------------------------------
// kotoba-lang/webgpu PR #9's technique (cross-platform `chromium.executablePath()`, not a
// hand-rolled macOS-only ~/Library/Caches/ms-playwright walk) — reapplied inline here the
// same way kami-app-isekai's own CI does for `kbb -M:render-test` (see .github/workflows/ci.yml),
// since that PR wasn't merged to webgpu main at the time this was written.
function findChromiumExe() {
  if (process.env.PW_EXE) return process.env.PW_EXE;
  try { return chromium.executablePath(); } catch (_e) { return undefined; }
}

// ---- tiny static file server (serves REPO_ROOT so relative fetches in game.cljs —
// "dev/out/game.js", "public/games/slime-hunt/scene.edn" — resolve exactly like the
// documented `python3 -m http.server` dev workflow, see README) --------------------------
const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.mjs': 'text/javascript',
  '.edn': 'text/plain; charset=utf-8', '.cljc': 'text/plain; charset=utf-8',
  '.cljs': 'text/plain; charset=utf-8', '.json': 'application/json', '.css': 'text/css',
  '.wasm': 'application/wasm', '.map': 'application/json',
};
function startServer(root, port) {
  return new Promise((resolve, reject) => {
    const server = createServer(async (req, res) => {
      try {
        const urlPath = decodeURIComponent((req.url || '/').split('?')[0]);
        const rel = urlPath === '/' ? 'game.html' : urlPath.replace(/^\/+/, '');
        const filePath = path.resolve(root, rel);
        if (!filePath.startsWith(root)) { res.writeHead(403); res.end('forbidden'); return; }
        const data = await readFile(filePath);
        const ext = path.extname(filePath);
        res.writeHead(200, { 'content-type': MIME[ext] || 'application/octet-stream' });
        res.end(data);
      } catch (_e) {
        res.writeHead(404); res.end('not found');
      }
    });
    server.on('error', reject);
    server.listen(port, '127.0.0.1', () => resolve(server));
  });
}

// ---- game control: read the window.__slimeHunt* debug hooks + drive real keyboard --------
const DIR_KEYS = { up: 'ArrowUp', down: 'ArrowDown', left: 'ArrowLeft', right: 'ArrowRight' };

async function readState(page) {
  return page.evaluate(() => ({
    phase: window.__slimeHuntPhase || null,
    status: window.__slimeHuntStatus || null,
    snap: window.__slimeHuntSnapshot ? window.__slimeHuntSnapshot() : [],
    globals: window.__slimeHuntGlobals ? window.__slimeHuntGlobals() : {},
  }));
}
const byTag = (snap, tag) => (snap || []).filter((e) => e.tag === tag);
function nearest(fromPos, entities) {
  let best = null, bestD = Infinity;
  for (const e of entities) {
    const [x, y] = e.pos;
    const d = Math.hypot(x - fromPos[0], y - fromPos[1]);
    if (d < bestD) { bestD = d; best = e; }
  }
  return best;
}

async function setHeld(page, held, wantSet) {
  for (const dir of Object.keys(DIR_KEYS)) {
    const want = wantSet.has(dir), have = held.has(dir);
    if (want && !have) { await page.keyboard.down(DIR_KEYS[dir]); held.add(dir); }
    else if (!want && have) { await page.keyboard.up(DIR_KEYS[dir]); held.delete(dir); }
  }
}
async function releaseAll(page, held) { await setHeld(page, held, new Set()); }

/** Closed-loop steer-toward-target controller. `pickTarget(state)` returns [x,y] or null
 *  (nothing to seek right now); `onState(state)` fires every poll for side effects
 *  (screenshots); `isDone(state)` ends the loop. Recomputes the target every poll (not a
 *  one-shot waypoint) so orb consumption / slime motion don't strand the controller. */
async function controlLoop(page, held, { pickTarget, onState, isDone, maxMs = 20000, pollMs = 70, deadzone = 10 }) {
  const start = Date.now();
  let state = await readState(page);
  while (Date.now() - start < maxMs) {
    state = await readState(page);
    if (onState) await onState(state);
    if (isDone(state)) { await releaseAll(page, held); return state; }
    const player = byTag(state.snap, 'player')[0];
    const target = player ? pickTarget(state, player) : null;
    if (!player || !target) {
      await setHeld(page, held, new Set());
      await page.waitForTimeout(pollMs);
      continue;
    }
    const [px, py] = player.pos, [tx, ty] = target;
    const dx = tx - px, dy = ty - py;
    const want = new Set();
    if (dx > deadzone) want.add('right'); else if (dx < -deadzone) want.add('left');
    if (dy > deadzone) want.add('up'); else if (dy < -deadzone) want.add('down');
    await setHeld(page, held, want);
    await page.waitForTimeout(pollMs);
  }
  await releaseAll(page, held);
  return state;
}

async function waitForPhase(page, phase, timeoutMs = 10000) {
  await page.waitForFunction((p) => window.__slimeHuntPhase === p, phase, { timeout: timeoutMs });
}

async function shoot(page, outDir, name, shots) {
  const file = path.join(outDir, `${name}.png`);
  // timeout: 60000 (vs Playwright's own 30000ms default) -- a cold full-page screenshot's
  // compositor/rasterize pass can genuinely need >30s under real concurrent-agent system load
  // (observed live during a network-isekai playtest-coscientist run tonight, load avg 170+;
  // fixed there the same way, see kotoba-lang/playwright#1) even though the page itself isn't
  // stuck -- a fixed 30s timeout with no override would abort the whole round for no real reason.
  await page.screenshot({ path: file, timeout: 60000 });
  // Capture the SAME window.__slimeHunt* debug-hook state readState() already reads for the
  // controller, at this exact screenshot instant — the "actual game state" half of the
  // murakumo structured-state critic's prompt (kami-app-isekai.playtest.vision-score/
  // structured-state-critique). `state` here is the readState() shape: {phase status snap
  // globals}; JSON.stringify'd through this script's own summary line, so the CLJ side gets
  // it as a plain EDN-able (keywordized) map with no extra wiring.
  const state = await readState(page);
  shots.push({ name, path: file, state });
  return file;
}

async function startPlay(page) {
  // mount-flow! (game.cljs) treats a real Space keydown identically to a click: resumes
  // audio, flips :title -> :play, hides the overlay. A trusted CDP keyboard event (not a
  // synthetic dispatchEvent) counts as a real user gesture for the AudioContext.resume()
  // autoplay-policy check.
  await page.keyboard.press(' ');
  await waitForPhase(page, 'play', 15000);
}

/** Episode: collect all 8 orbs while steering away from awakened slimes as a secondary
 *  avoidance term (best-effort — logic.cljc's wake-range/hit-range are real, so a slime
 *  that wakes mid-lap CAN still land a hit; that's fine, it doesn't invalidate the victory
 *  screenshot, it's just not the "lose" episode's job to guarantee zero damage). */
async function runVictoryEpisode(page, outDir, shots) {
  await shoot(page, outDir, 'title', shots);
  await startPlay(page);
  const held = new Set();
  let shotPickup = false;
  const result = await controlLoop(page, held, {
    maxMs: 90000,
    pollMs: 70,
    onState: async (state) => {
      const picked = byTag(state.snap, 'picked').length;
      if (!shotPickup && picked > 0) { shotPickup = true; await shoot(page, outDir, 'pickup', shots); }
    },
    isDone: (state) => state.phase === 'victory' || state.phase === 'gameover',
    pickTarget: (state, player) => {
      const orbs = byTag(state.snap, 'orb');
      const slimes = [
        ...byTag(state.snap, 'slime-green'),
        ...byTag(state.snap, 'slime-fire'),
        ...byTag(state.snap, 'slime-ice'),
      ];
      if (orbs.length === 0) return null;
      const orb = nearest(player.pos, orbs);
      const threat = nearest(player.pos, slimes);
      if (threat) {
        const d = Math.hypot(threat.pos[0] - player.pos[0], threat.pos[1] - player.pos[1]);
        // Inside wake-range (300 world-units, logic.cljc) — steer AWAY from the slime instead
        // of straight at the next orb, so the victory run stays clean whenever it's easy to.
        if (d < 260) {
          return [player.pos[0] + (player.pos[0] - threat.pos[0]), player.pos[1] + (player.pos[1] - threat.pos[1])];
        }
      }
      return orb.pos;
    },
  });
  if (result.phase === 'victory') {
    await waitForPhase(page, 'victory', 5000).catch(() => {});
    await shoot(page, outDir, 'victory', shots);
  }
  return { phase: result.phase, pickedShot: shotPickup, picked: byTag(result.snap, 'picked').length };
}

/** Episode: deliberately walk into the nearest slime, repeatedly, until 3 hits drain all
 *  lives and :gameover fires. */
async function runLoseEpisode(page, outDir, shots) {
  await startPlay(page);
  const held = new Set();
  let shotHit = false;
  let lastLives = byTag((await readState(page)).snap, 'life').length;
  const result = await controlLoop(page, held, {
    maxMs: 60000,
    pollMs: 70,
    onState: async (state) => {
      const lives = byTag(state.snap, 'life').length;
      if (lives < lastLives) {
        if (!shotHit) { shotHit = true; await shoot(page, outDir, 'hit', shots); }
        lastLives = lives;
      }
    },
    isDone: (state) => state.phase === 'gameover' || state.phase === 'victory',
    pickTarget: (state, player) => {
      const slimes = [
        ...byTag(state.snap, 'slime-green'),
        ...byTag(state.snap, 'slime-fire'),
        ...byTag(state.snap, 'slime-ice'),
      ];
      if (slimes.length === 0) return null;
      return nearest(player.pos, slimes).pos;
    },
  });
  if (result.phase === 'gameover') {
    await waitForPhase(page, 'gameover', 5000).catch(() => {});
    await shoot(page, outDir, 'gameover', shots);
  }
  return { phase: result.phase, hitShot: shotHit, livesLeft: byTag(result.snap, 'life').length };
}

// ---- main ---------------------------------------------------------------------------------
async function main() {
  await mkdir(OUT_DIR, { recursive: true });
  const server = await startServer(REPO_ROOT, args.port);
  const port = server.address().port;
  const baseUrl = `http://127.0.0.1:${port}/game.html`;

  const browser = await chromium.launch({
    headless: !args.headed,
    executablePath: findChromiumExe(),
    args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
           '--ignore-gpu-blocklist', '--enable-webgl'],
  });
  const shots = [];
  try {
    // ---- episode 1: victory (also produces title + pickup) ----
    const ctx1 = await browser.newContext({ viewport: { width: 1000, height: 1080 } });
    const page1 = await ctx1.newPage();
    await page1.goto(baseUrl, { waitUntil: 'domcontentloaded' });
    await page1.waitForFunction(() => window.__slimeHuntPhase === 'title', null, { timeout: 15000 });
    const victory = await runVictoryEpisode(page1, OUT_DIR, shots);
    await ctx1.close();

    // ---- episode 2: lose (also produces hit + game-over) ----
    const ctx2 = await browser.newContext({ viewport: { width: 1000, height: 1080 } });
    const page2 = await ctx2.newPage();
    await page2.goto(baseUrl, { waitUntil: 'domcontentloaded' });
    await page2.waitForFunction(() => window.__slimeHuntPhase === 'title', null, { timeout: 15000 });
    const lose = await runLoseEpisode(page2, OUT_DIR, shots);
    await ctx2.close();

    const summary = { ok: true, outDir: OUT_DIR, baseUrl, shots, victory, lose };
    console.log(JSON.stringify(summary));
    return summary;
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
}

main().catch((e) => {
  console.log(JSON.stringify({ ok: false, error: String((e && e.stack) || e) }));
  process.exitCode = 1;
});
