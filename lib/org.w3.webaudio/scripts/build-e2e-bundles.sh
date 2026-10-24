#!/usr/bin/env bash
# Compiles the two bundles needed for the org-w3-webaudio real-browser
# AudioWorkletProcessor E2E (test/e2e/run_e2e.cljk):
#
#   1. test/e2e/src/w3/webaudio/e2e/main_driver.cljk -> main-thread bundle
#      (page/main-driver-bundle.js). Uses this repo's own src/w3/webaudio.cljk
#      binding layer to drive AudioContext/OfflineAudioContext/AudioWorkletNode
#      from the page.
#   2. test/e2e/src/w3/webaudio/e2e/worklet_dsp.cljk -> worklet-side bundle
#      (page/worklet-processor.js). Requires kotoba-lang/audio's audio.synth
#      -- the .cljc DSP source of truth -- directly, and exports a
#      render-note entrypoint consumed by the hand-written
#      AudioWorkletProcessor registration in page/worklet-processor-tail.js.
#
# Both MUST compile with --optimizations advanced. This is not just an
# optimization choice -- it is the actual fix for the blocker this repo's
# README previously documented ("a ClojureScript/Closure-compiled bundle
# cannot be loaded as part of an AudioWorkletProcessor module"):
#
#   Root cause #1 (affects :none/:simple/:whitespace): cljs.main's default
#   build bundles `clojure.browser.repl`'s dev REPL-connect bootstrap, which
#   unconditionally constructs a goog.net.xpc.CrossPageChannel ->
#   goog.dom.DomHelper -> `document` reference at module top-level.
#   AudioWorkletGlobalScope has no `document` (no DOM), so this throws a
#   ReferenceError while the module is evaluating -- BEFORE any of the
#   module's own code (including registerProcessor) runs. Per the Worklets
#   spec (as implemented here), this does not reject audioWorklet.addModule's
#   promise and produces no console/pageerror event, so it is silent: the
#   symptom is exactly "registerProcessor never seems to run", which is what
#   the previous investigation observed and correctly attributed to
#   "something Closure/goog-bootstrap-shaped", without root-causing the
#   specific `document` access. Verified empirically (not guessed): wrapping
#   a :simple build in try/catch and reporting the caught error via
#   port.postMessage surfaces exactly this stack trace. :optimizations
#   :advanced's whole-program dead-code elimination proves the REPL-connect
#   call is unreachable in a real (non-dev, non-`-r`) build and removes it
#   entirely -- confirmed via grep: 0 matches for
#   "clojure.browser.repl"/"goog.net.xpc"/"DomHelper" in an :advanced build,
#   97-116 matches in :simple/:whitespace builds of the identical namespace.
#
#   Root cause #2 (only bites once real cross-boundary calls are needed --
#   i.e. any `^:export`, which both bundles here use to be callable from
#   hand-written JS the Closure compiler never sees): Closure's own
#   goog.global detection (`goog.global = this || self`, which
#   goog.exportSymbol -- the mechanism ^:export compiles to -- depends on)
#   still runs whenever anything in the build needs goog.global. Bare `self`
#   is genuinely undeclared in AudioWorkletGlobalScope (WorkletGlobalScope,
#   unlike WorkerGlobalScope, does not define `self`), so referencing it
#   throws ReferenceError. This reproduces even under :advanced once
#   anything (an export, in our case) keeps the goog.global assignment from
#   being dead-code-eliminated -- an :advanced build with ZERO exports
#   "happens to work" only because DCE also removes the otherwise-unused
#   goog.global line, which is a coincidence of that build having nothing to
#   export, not evidence :advanced alone fixes the environment gap. The fix
#   (test/e2e/page/self-polyfill.js, prepended to both bundles) is the
#   standard technique non-browser JS runtimes use for browser-oriented code
#   (e.g. Node has historically polyfilled `global.self = global`):
#     if (typeof self === "undefined") { globalThis.self = globalThis; }
#   `typeof self` is the ReferenceError-safe form of the same check.
#
#   Aside, tried and rejected: a plain `(set! (.-x js/goog.global) f)`
#   manual property write instead of `^:export` looks equivalent but is NOT
#   DCE-safe -- it worked in one bundle here and got silently eliminated
#   (function body and all) in the other, for reasons that trace back to
#   Closure only special-casing `goog.exportSymbol` itself as always-keep.
#   Use ^:export, not a manual global write.
#
# Neither of these is fixed by `--target webworker`/`--target none`: both
# were tried and still include the clojure.browser.repl bootstrap under
# :simple (cljs.main injects it based on optimization level, not --target).
#
# Requires the Clojure CLI (JVM) -- the ClojureScript compiler itself runs on
# the JVM; this is a BUILD-time tool only, not an app-runtime choice.
set -euo pipefail
cd "$(dirname "$0")/.."

rm -rf test/e2e/.build-main test/e2e/.build-worklet
mkdir -p test/e2e/page

echo "compiling main-thread driver bundle (w3.webaudio.e2e.main-driver)..."
kbb -M:e2e -m cljs.main -d test/e2e/.build-main \
  --optimizations advanced \
  --output-to test/e2e/page/main-driver-bundle.raw.js \
  -c w3.webaudio.e2e.main-driver
cat test/e2e/page/self-polyfill.js test/e2e/page/main-driver-bundle.raw.js \
    > test/e2e/page/main-driver-bundle.js
rm -f test/e2e/page/main-driver-bundle.raw.js

echo "compiling worklet DSP bundle (w3.webaudio.e2e.worklet-dsp)..."
kbb -M:e2e -m cljs.main -d test/e2e/.build-worklet \
  --optimizations advanced \
  --output-to test/e2e/page/worklet-dsp-bundle.raw.js \
  -c w3.webaudio.e2e.worklet-dsp
cat test/e2e/page/self-polyfill.js \
    test/e2e/page/worklet-dsp-bundle.raw.js \
    test/e2e/page/worklet-processor-tail.js \
    > test/e2e/page/worklet-processor.js
rm -f test/e2e/page/worklet-dsp-bundle.raw.js

echo "wrote test/e2e/page/main-driver-bundle.js and test/e2e/page/worklet-processor.js"
