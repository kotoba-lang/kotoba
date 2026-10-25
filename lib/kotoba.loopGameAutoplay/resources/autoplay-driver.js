/* autoplay-driver.js — the agent channel.
 *
 * Injected into an UNMODIFIED game page. The game keeps its own state, its own
 * update(), its own rendering; this file only reads that state, writes the key
 * map the game already polls, and (in train mode) drives update() directly
 * instead of waiting for the wall clock.
 *
 * Why this is plain browser JavaScript in a workspace whose rule is "no new
 * .mjs/.cjs, write nbb":
 *
 *   That rule governs Node scripts. This file is neither a Node script nor
 *   ours to compile: it has to run inside a page that has no build step, and
 *   the SAME bytes have to be served to Safari on a booted iOS Simulator,
 *   where there is no ClojureScript toolchain and no remote-eval channel.
 *
 *   The part that would be dangerous to duplicate in JS -- what a policy IS --
 *   is not duplicated. `act()` below computes a = W.obs + b with w row-major
 *   [act][obs], which is `shugyo.policy/act-batch` from
 *   kotoba-lang/com-nvidia-isaac-lab. That cljc function is the oracle and
 *   `policy_parity_test` runs both over the same random weights and asserts
 *   agreement to 1e-12. This file is a qualified fast path, not a second
 *   definition.
 *
 * Contract with the host page (survivors-zombie.html and anything shaped like
 * it): globals `G`, `keys`, `update(dt)`, `newGame()`, `applyDraft(o)`,
 * `startLoop()`, `SPEC`. Classic <script> top-level `let`/`const` live in the
 * global lexical environment, so they resolve as bare identifiers here.
 */
(function () {
  'use strict';

  // ---------------------------------------------------------------- rng ----
  // Seeded PRNG replacing Math.random so an episode replays exactly. This does
  // NOT have to match shinka.rng: the game's randomness only needs to be
  // reproducible, not shared with the search.
  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  var OBS_DIM = 12;
  var ACT_DIM = 5;          // [move-x, move-y, draft-0, draft-1, draft-2]
  var STEP = 0.02;          // seconds; the game's own sub-step size
  var PICK_THRESHOLD = 0.3; // |axis| above which a direction key is held

  // -------------------------------------------------------- observation ----
  function nearest(list, x, y) {
    var best = null, bd = Infinity;
    for (var i = 0; i < list.length; i++) {
      var dx = list[i].x - x, dy = list[i].y - y, d = dx * dx + dy * dy;
      if (d < bd) { bd = d; best = list[i]; }
    }
    return best ? { e: best, d: Math.sqrt(bd) } : null;
  }

  /* 12 numbers, all roughly in [-1,1]. Deliberately state-based, not pixels:
   * a pixel observation would make the policy depend on resolution, theme and
   * device scale, and this same policy has to run on a phone screen. */
  function observe() {
    var p = G.player;
    var ne = nearest(G.enemies, p.x, p.y);
    var ng = nearest(G.gems, p.x, p.y);
    var density = 0;
    for (var i = 0; i < G.enemies.length; i++) {
      var dx = G.enemies[i].x - p.x, dy = G.enemies[i].y - p.y;
      if (dx * dx + dy * dy < 200 * 200) density++;
    }
    var o = new Array(OBS_DIM);
    o[0] = p.hp / p.maxhp;
    o[1] = Math.min(1, G.t / SPEC.win.survive_ms);
    o[2] = Math.min(1, G.level / 20);
    o[3] = Math.min(1, G.xp / Math.max(1, G.xpNext));
    o[4] = ne ? (ne.e.x - p.x) / Math.max(1, ne.d) : 0;
    o[5] = ne ? (ne.e.y - p.y) / Math.max(1, ne.d) : 0;
    o[6] = ne ? Math.min(1, ne.d / 600) : 1;
    o[7] = Math.min(1, G.enemies.length / 60);
    o[8] = ng ? (ng.e.x - p.x) / Math.max(1, ng.d) : 0;
    o[9] = ng ? (ng.e.y - p.y) / Math.max(1, ng.d) : 0;
    o[10] = ng ? Math.min(1, ng.d / 600) : 1;
    o[11] = Math.min(1, density / 20);
    return o;
  }

  // ------------------------------------------------------------- policy ----
  /* a = W.obs + b, w row-major w[a * obsDim + o]. Mirror of
   * shugyo.policy/act-batch for num-envs = 1. */
  function act(policy, obs) {
    var w = policy.w, b = policy.b, out = new Array(ACT_DIM);
    for (var a = 0; a < ACT_DIM; a++) {
      var acc = b[a], base = a * OBS_DIM;
      for (var o = 0; o < OBS_DIM; o++) acc += w[base + o] * obs[o];
      out[a] = acc;
    }
    return out;
  }

  function applyKeys(a) {
    keys['d'] = a[0] > PICK_THRESHOLD ? 1 : 0;
    keys['a'] = a[0] < -PICK_THRESHOLD ? 1 : 0;
    keys['s'] = a[1] > PICK_THRESHOLD ? 1 : 0;
    keys['w'] = a[1] < -PICK_THRESHOLD ? 1 : 0;
  }

  /* The level-up draft is a real decision, so the policy makes it: three
   * outputs score the three offered cards and the highest wins. Clicking the
   * card is how the game itself resolves a draft, so no game code is bypassed. */
  function resolveDraft(a) {
    var cards = document.querySelectorAll('#overlay .card');
    if (!cards.length) return false;
    var bestI = 0, bestV = -Infinity;
    for (var i = 0; i < cards.length && i < 3; i++) {
      var v = a[2 + i];
      if (v > bestV) { bestV = v; bestI = i; }
    }
    cards[bestI].click();
    return true;
  }

  // ------------------------------------------------------------ episode ----
  function fitness(res) {
    // Survival is the objective; level rewards actually engaging rather than
    // running in circles, and the win bonus is large enough that surviving to
    // the end always beats any amount of levelling that did not.
    return res.survivedMs / 1000 + 2 * res.level + (res.won ? 300 : 0);
  }

  /* Headless: drive update() directly at a fixed step, never render, never
   * wait for the clock. Returns the run's result + fitness. */
  function episode(policy, seed, maxSimMs) {
    var realRandom = Math.random;
    Math.random = mulberry32(seed >>> 0);
    requirePolicy(policy);
    try {
      newGame();
      G.running = true;
      var steps = 0, cap = Math.ceil((maxSimMs / 1000) / STEP);
      while (steps < cap) {
        if (G.lvlpending) { if (!resolveDraft(act(policy, observe()))) break; }
        if (!G.running || G.over) break;
        applyKeys(act(policy, observe()));
        update(STEP);
        steps++;
      }
      var res = {
        survivedMs: G.t, level: G.level, hp: G.player.hp,
        won: !!G.won, over: !!G.over, steps: steps,
        truncated: steps >= cap && !G.over
      };
      res.fitness = fitness(res);
      return res;
    } finally {
      Math.random = realRandom;
      for (var k in keys) keys[k] = 0;
    }
  }

  /* Real time: let the game run its OWN loop -- its own setInterval, its own
   * draw() -- and only steer. This is the mode that gets recorded, because a
   * video of the headless path would be a video of nothing. */
  /* The training path builds this with loop-game-autoplay.policy/genome->policy
   * and the device path builds it from a query string. They disagreed once --
   * the device was handed the flat genome instead -- and the only symptom was
   * a game that played itself with no input until a level-up modal blocked it
   * forever. Nothing threw where anyone could see it. Check the shape. */
  function requirePolicy(policy) {
    var ok = policy && Array.isArray(policy.w) && Array.isArray(policy.b) &&
             policy.w.length === OBS_DIM * ACT_DIM && policy.b.length === ACT_DIM;
    if (!ok) {
      throw new Error('bad policy: expected {w:[' + (OBS_DIM * ACT_DIM) + '], b:[' +
                      ACT_DIM + ']}, got ' + JSON.stringify(policy).slice(0, 120));
    }
    return policy;
  }

  function play(policy, seed) {
    requirePolicy(policy);
    Math.random = mulberry32(seed >>> 0);
    newGame();
    G.running = true;
    document.getElementById('overlay').innerHTML = '';
    startLoop();
    // Tell the server the phone actually got this far. Without it, a run that
    // never finishes is indistinguishable from a page that never loaded --
    // and on the Simulator there is no other way to tell them apart.
    report({ phase: 'start', seed: seed, ua: navigator.userAgent,
             screen: { w: innerWidth, h: innerHeight, dpr: window.devicePixelRatio || 1 } });
    var handle = setInterval(function () {
     try {
      if (G.lvlpending) { resolveDraft(act(policy, observe())); return; }
      if (!G.running || G.over) {
        clearInterval(handle);
        var res = {
          phase: 'end',
          survivedMs: G.t, level: G.level, hp: G.player.hp,
          won: !!G.won, over: !!G.over, steps: null, truncated: false,
          mode: 'play', ua: navigator.userAgent,
          screen: { w: innerWidth, h: innerHeight, dpr: window.devicePixelRatio || 1 }
        };
        res.fitness = fitness(res);
        window.__autoplay.done = true;
        window.__autoplay.result = res;
        // The only channel back from Safari on a booted Simulator: there is
        // no remote eval, so the page reports its own outcome to the server
        // that served it. Without this the recorder would have to guess how
        // long the run lasted.
        report(res);
        return;
      }
      applyKeys(act(policy, observe()));
     } catch (e) {
      // An exception inside setInterval is invisible: the callback dies, the
      // interval keeps firing, and the game keeps running with no input. That
      // is exactly how a 20-minute recording of a frozen level-up modal
      // happened. Say so, once, and stop.
      clearInterval(handle);
      window.__autoplay.error = String(e);
      report({ phase: 'error', error: String(e), survivedMs: (typeof G !== 'undefined' ? G.t : null) });
     }
    }, 16);
    return true;
  }

  function report(res) {
    try {
      fetch('/result', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(res)
      });
    } catch (e) { /* a lost report must not take the run down with it */ }
  }

  window.__autoplay = {
    version: 'autoplay-driver/v1',
    obsDim: OBS_DIM, actDim: ACT_DIM,
    observe: observe, act: act, episode: episode, play: play,
    done: false,
    ready: typeof G !== 'undefined' || true
  };

  // Self-start when the page was opened with ?genome=...  This is the path the
  // iOS Simulator uses: openurl is the only channel, so the page has to start
  // itself. Playwright does not use it -- it calls episode() directly.
  var q = new URLSearchParams(location.search);
  if (q.get('mode') === 'play' && q.get('genome')) {
    var g = JSON.parse(decodeURIComponent(q.get('genome')));
    var seed = parseInt(q.get('seed') || '1', 10);
    window.addEventListener('load', function () {
      setTimeout(function () {
        try { play(g, seed); }
        catch (e) { window.__autoplay.error = String(e); report({ phase: 'error', error: String(e) }); }
      }, 300);
    });
  }
})();
