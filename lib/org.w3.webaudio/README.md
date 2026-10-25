# kotoba-lang/org-w3-webaudio

Raw **W3C Web Audio API** JS surface — a thin ClojureScript wrapper, one
function per spec call, in the same narrow-scope-binding-repo pattern as
`kotoba-lang/org-w3-webgpu` (itself factored out of `kotoba-lang/webgpu` per
ADR-2607051400, `com-junkawasaki/root`). This repo is the audio-domain
sibling defined by ADR-2607121400 (`90-docs/adr/2607121400-kami-ongaku-eizo-commercial-grade-cljs-stack.md`).

## Why this repo exists

`kotoba-lang/audio` (KAMI Audio) is the DSP executor for the `ongaku`
domain — synthesis, effects, mixer bus, offline PCM render. It should not
call `AudioContext`/`AudioWorkletNode`/... inline any more than
`kotoba-lang/webgpu` should call `navigator.gpu` inline. This repo is that
boundary: **just the raw spec surface**, no synthesis/effects/mixer
opinions — those stay in `audio`.

**Scope is deliberately narrow, mirroring org-w3-webgpu exactly:**

- `src/w3/webaudio.cljk` — `AudioContext` lifecycle (create/resume/suspend/
  close), `AudioWorkletNode` creation + `audioWorklet.addModule`, node
  `connect!`/`disconnect!`, `GainNode`/`AudioBuffer`/`AudioBufferSourceNode`
  creation, and the `AudioWorkletNode.port` (MessagePort) primitives
  (`post-message!`/`on-message!`). Descriptors/options are plain JS objects
  built by the caller, same non-translation stance as org-w3-webgpu.
- `src/w3/webaudio/protocol.cljk` — **portable** (JVM + cljs) encode/decode
  for the small control-message envelope sent across the worklet
  `MessagePort` (note-on/note-off/param-change/pcm-block/ack/error). PCM
  sample data itself is a `Float32Array` and crosses the port directly
  (optionally as a Transferable); this namespace only frames the control
  messages — the one part of the port boundary with no browser-only API
  surface, and therefore the one part of this repo that unit tests can
  actually exercise.

## Status

**v0, thin binding layer only — no DSP.** `AudioContext`/`AudioWorkletNode`
only exist in a real browser, so `w3/webaudio.cljs` (like org-w3-webgpu's
`w3/webgpu.cljs`) has no JVM test suite. `w3/webaudio/protocol.cljc` **is**
unit tested (portable, no browser needed):

```
kbb -M:test
Ran 4 tests containing 17 assertions.
0 failures, 0 errors.
```

### Real-browser verification (Wave 5, 2026-07-12)

Actually exercised against a real headless Chromium via Playwright
(`kotoba-lang/playwright`), compiled with `cljs.main`:

- **`new-audio-context!` was broken and is now fixed.** `(new (ctor) opts)`
  — calling a private 0-arg fn to get the constructor, then `new`-ing the
  *call expression* — mis-compiles to `(new w3.webaudio.ctor.call(null))(opts)`
  (a `new` over the bare `.call` property, then invoking the result), which
  threw `TypeError: ... .call is not a constructor` on every invocation,
  in every browser, regardless of `opts`. This had shipped since Wave 2
  without being caught, because this file has no JVM test suite by design.
  Fixed by binding the constructor to a local before `new`-ing it. Verified
  fixed against real Chromium (`ctx.sampleRate` returned correctly).
- **`new-offline-audio-context!` + `start-rendering!` added** (this
  addition) and verified working in real Chromium — `OfflineAudioContext`
  is the only way to exercise Web Audio deterministically without a real
  audio output device, which headless environments don't have.
- **`audioWorklet` availability requires a secure context.** `about:blank`
  pages are *not* secure contexts by default in this Playwright/Chromium
  setup (`window.isSecureContext === false`), and `BaseAudioContext`
  doesn't even expose the `audioWorklet` property in that case. Serving
  the test page from `http://localhost` fixes this (`localhost` counts as
  a secure context). Anyone writing real browser tests against this repo
  needs a local static server, not `page.evaluate` on a blank page.
- **Known blocker, not fixed here: a ClojureScript/Closure-compiled
  bundle cannot be loaded as part of an `AudioWorkletProcessor` module in
  this environment.** `audioWorklet.addModule()` resolves without
  rejecting, but any code placed *after* a `cljs.main`-compiled bundle in
  the same worklet module file never runs (confirmed with a trivial
  single-function namespace, not specific to this repo's own code size or
  complexity) — `registerProcessor(...)` is never reached, so the node
  fails to construct with "not defined in AudioWorkletGlobalScope". This
  reproduces with `:optimizations` `:simple` and `:whitespace` alike.
  Isolated via bisection (all confirmed empirically, not guessed):
  - The same bundle loads fine as a dynamically-imported ES module on the
    **main thread**, including code appended after it.
  - A non-Closure plain-JS file of comparable/larger size, with
    `registerProcessor` appended, works fine **inside the worklet**.
  - A `cljs.main`-compiled bundle for a *trivial* one-function namespace
    (no DSP, no protocol code) still breaks trailing code **inside the
    worklet**.
  - So it's specifically "Closure/goog-bootstrapped code inside
    `AudioWorkletGlobalScope`" that's the problem, not bundle size and not
    this repo's own code. No `pageerror`/`console` event surfaces the
    actual failure (Closure's own `goog.require` "could not find" console
    warnings are a red herring — they come from `main-compiled.js` loaded
    on the *main page*, not from inside the worklet, and are non-fatal in
    both places).
  - **Root cause not further isolated** — would need Chromium-internal
    worklet-thread debugging tools beyond what Playwright's page-level API
    exposes. This blocks the ADR-2607121400 completion-gate item "実ブラウザ
    E2E: 音楽は AudioWorklet 経由の実 PCM render" for a cljs-compiled
    worklet processor specifically; a hand-written-JS processor (as used
    by the isolation tests above) is unaffected.

### Blocker resolved (Wave 6, 2026-07-12) — real AudioWorklet DSP E2E passing

The Wave 5 blocker above is fixed. Two distinct, empirically-isolated root
causes (not one) were behind "registerProcessor never runs, no error
surfaces" — see `scripts/build-e2e-bundles.sh` for the full derivation, not
repeated in full here:

1. **`cljs.main`'s default build bundles `clojure.browser.repl`'s dev
   REPL-connect bootstrap**, which unconditionally constructs a
   `goog.net.xpc.CrossPageChannel` → `goog.dom.DomHelper` → `document`
   reference at module top-level. `AudioWorkletGlobalScope` has no
   `document`, so this throws a `ReferenceError` while the module is
   *evaluating*, before any of the module's own code (including
   `registerProcessor`) runs. In this environment that does not reject
   `audioWorklet.addModule`'s promise and produces no console/pageerror
   event, matching exactly the "silent" symptom previously observed.
   Confirmed by wrapping a `:simple` build in try/catch and reporting the
   caught error via `port.postMessage`:
   ```
   ReferenceError: document is not defined
       at new goog.dom.DomHelper (...)
       at goog.dom.getDomHelper (...)
       at new goog.net.xpc.CrossPageChannel (...)
       at clojure.browser.net.xpc_connection (...)
       at clojure.browser.repl.connect (...)
   ```
   `--optimizations advanced`'s whole-program dead-code elimination proves
   this call unreachable in a real (non-`-r`) build and removes it
   entirely — confirmed via grep: 0 matches for
   `clojure.browser.repl`/`goog.net.xpc`/`DomHelper` in an `:advanced`
   build vs. 97-116 matches in `:simple`/`:whitespace` builds of the
   identical namespace. **This is the actual fix for the Wave 5 blocker as
   originally reported** ("reproduces with `:simple` and `:whitespace`
   alike"): compile the worklet-side bundle with `:optimizations advanced`.
   `--target webworker`/`--target none` do **not** fix this (both tried;
   `cljs.main` injects the REPL bootstrap based on optimization level, not
   `--target`).
2. **Once real cross-boundary calls are needed** (any `^:export`, required
   for hand-written JS the Closure compiler never sees to call back into
   the compiled bundle — e.g. the `AudioWorkletProcessor` tail calling the
   compiled DSP render function), Closure's own `goog.global` detection
   (`goog.global = this || self`, which `goog.exportSymbol`/`^:export`
   depends on) runs, and bare `self` is genuinely undeclared in
   `AudioWorkletGlobalScope` (`WorkletGlobalScope`, unlike
   `WorkerGlobalScope`, does not define `self`) — referencing it throws
   `ReferenceError`. This reproduces even under `:advanced` once anything
   keeps the `goog.global` assignment from being dead-code-eliminated (a
   no-export `:advanced` build "happens to work" only because DCE also
   removes the otherwise-unused `goog.global` line — a coincidence of
   nothing being exported, not evidence `:advanced` alone closes the
   environment gap). Fix: prepend one polyfill line (the
   `ReferenceError`-safe `typeof` guard) before the compiled bundle in the
   same worklet module file — the standard technique non-browser JS
   runtimes use for browser-oriented code (e.g. Node has historically
   polyfilled `global.self = global`):
   ```js
   if (typeof self === "undefined") { globalThis.self = globalThis; }
   ```
   Tried and rejected: a plain `(set! (.-x js/goog.global) f)` manual
   property write instead of `^:export` looks equivalent but is **not**
   safe against Closure's DCE — it survived in one bundle here and was
   silently eliminated (function body and all, no export, no error) in
   another with an outwardly identical shape. Use `^:export`
   (`goog.exportSymbol`), not a manual global write — it's the one
   mechanism Closure's optimizer passes explicitly special-case as
   always-keep.

**Real E2E** (`test/e2e/`, `scripts/build-e2e-bundles.sh` +
`test/e2e/run_e2e.cljk`): a worklet-side bundle
(`w3.webaudio.e2e.worklet-dsp`) requires `kotoba-lang/audio`'s own
`audio.synth` directly (not a reimplementation) and exports a
`render-note` entrypoint; a hand-written `AudioWorkletProcessor` subclass
(real ES6 `class ... extends`, native `super()`) calls it once in its
constructor and streams the precomputed buffer out through the realtime
`process()` quantum callback. A main-thread bundle
(`w3.webaudio.e2e.main-driver`) uses this repo's own `src/w3/webaudio.cljk`
binding layer (`new-offline-audio-context!`, `add-worklet-module!`,
`create-worklet-node!`, `connect!`, `start-rendering!`) to load the worklet
module into a real headless Chromium (Playwright,
`kotoba-lang/playwright`'s bridge pattern), render a 440 Hz sine through a
short ADSR envelope (0.2 s @ 48 kHz, attack 0.01 s / decay 0.02 s / sustain
0.6 / release 0.05 s starting at 0.15 s), and capture the actual rendered
PCM via `OfflineAudioContext`. `test/e2e/run_e2e.cljk` independently
computes the same note via `audio.synth` directly (no browser involved) as
the ground-truth reference, and diffs the two:

```
=== org-w3-webaudio real-browser AudioWorklet E2E result ===
captured length: 9600 reference length: 9600
first 10 captured: (0 0.00011992505460511893 0.00047890478163026273 0.0010745568433776498 ...)
first 10 reference: (0 0.00011992505616576517 0.00047890479372027754 0.0010745568767463098 ...)
max abs diff: 2.9777488363968985e-8 tolerance: 0.000001
PASS: true
```

The tiny (~3e-8) diff is exactly the expected `Float32Array` (worklet path,
single precision) vs. double-precision (reference) rounding, not a
correctness gap. Also worth noting, found along the way (not a cljs/Closure
issue): Playwright's `page.evaluate(pageFunction, arg)` silently drops
`arg` and resolves to `undefined` when `pageFunction` is passed as a source
**string** rather than an actual `Function` value — confirmed with plain
Node + Playwright, no ClojureScript/nbb involved. `run_e2e.cljs` works
around this by inlining the JSON params into the expression string instead
of using the separate `arg` parameter.

This closes the ADR-2607121400 completion-gate item "実ブラウザ E2E: 音楽は
AudioWorklet 経由の実 PCM render" for a genuinely cljs-compiled worklet
processor (not the hand-written-JS escape hatch the gate also allows for).

## Develop

```
kbb -M:test   ;; protocol.cljc only — webaudio.cljs needs a real browser

# Real-browser AudioWorklet DSP E2E (requires the Clojure CLI, Node, and a
# checkout of kotoba-lang/audio for the offline reference computation):
bash scripts/build-e2e-bundles.sh
npm --prefix test/e2e install
kbb --backend sci -cp "/path/to/kotoba-lang/audio/src" test/e2e/run_e2e.cljk
```
