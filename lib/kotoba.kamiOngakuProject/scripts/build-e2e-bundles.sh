#!/usr/bin/env bash
# Compiles the two bundles needed for kami-ongaku-project's real-browser
# AudioWorkletProcessor multi-track bus-graph MIXING E2E
# (test/e2e/run_e2e.cljk):
#
#   1. test/e2e/src/kami/ongaku/project/e2e/main_driver.cljk -> main-thread
#      bundle (page/main-driver-bundle.js). Uses kotoba-lang/org-w3-webaudio's
#      own src/w3/webaudio.cljs binding layer to drive OfflineAudioContext /
#      audioWorklet.addModule / AudioWorkletNode from the page.
#   2. test/e2e/src/kami/ongaku/project/e2e/worklet_dsp.cljk -> worklet-side
#      bundle (page/worklet-processor.js). Requires this repo's own
#      kami.ongaku.project (real track/bus/clip session + validate-project),
#      kami.ongaku.notation / kami.ongaku.sequencer (real per-track content,
#      via the shared test/e2e/src/kami/ongaku/project/e2e/fixture.cljk) and
#      kotoba-lang/audio's audio.synth (real oscillator + ADSR DSP), and
#      exports a render-mix entrypoint consumed by the hand-written
#      AudioWorkletProcessor registration in page/worklet-processor-tail.js.
#
# Both MUST compile with --optimizations advanced, and both MUST have
# page/self-polyfill.js prepended ahead of the compiled bundle in the same
# file. This is not a stylistic choice -- it is the fix for a real blocker
# fully root-caused and documented in kotoba-lang/org-w3-webaudio's own
# README + scripts/build-e2e-bundles.sh (reused verbatim here, not
# rediscovered):
#
#   1. cljs.main's default (non-:advanced) build bundles
#      clojure.browser.repl's dev REPL-connect bootstrap, which
#      unconditionally touches `document` at module top-level.
#      AudioWorkletGlobalScope has no `document` -- this throws a
#      ReferenceError while the module is *evaluating*, before
#      registerProcessor ever runs, and does so silently: no rejected
#      addModule() promise, no console/pageerror event. :optimizations
#      :advanced's whole-program DCE proves this call unreachable in a real
#      build and removes it entirely.
#   2. Once anything in the build needs goog.global (any ^:export does --
#      both bundles here export one function each), Closure's own
#      `goog.global = this || self` runs, and bare `self` is genuinely
#      undeclared in AudioWorkletGlobalScope (unlike WorkerGlobalScope).
#      Fix: prepend page/self-polyfill.js.
#
# See kotoba-lang/org-w3-webaudio's README ("Blocker resolved (Wave 6,
# 2026-07-12)") for the full empirical derivation.
#
# Requires the Clojure CLI (JVM) -- the ClojureScript compiler itself runs
# on the JVM; this is a BUILD-time tool only, not an app-runtime choice.
set -euo pipefail
cd "$(dirname "$0")/.."

rm -rf test/e2e/.build-main test/e2e/.build-worklet
mkdir -p test/e2e/page

echo "compiling main-thread driver bundle (kami.ongaku.project.e2e.main-driver)..."
kbb -M:e2e -m cljs.main -d test/e2e/.build-main \
  --optimizations advanced \
  --output-to test/e2e/page/main-driver-bundle.raw.js \
  -c kami.ongaku.project.e2e.main-driver
cat test/e2e/page/self-polyfill.js test/e2e/page/main-driver-bundle.raw.js \
    > test/e2e/page/main-driver-bundle.js
rm -f test/e2e/page/main-driver-bundle.raw.js

echo "compiling worklet DSP + bus-graph-mix bundle (kami.ongaku.project.e2e.worklet-dsp)..."
kbb -M:e2e -m cljs.main -d test/e2e/.build-worklet \
  --optimizations advanced \
  --output-to test/e2e/page/worklet-dsp-bundle.raw.js \
  -c kami.ongaku.project.e2e.worklet-dsp
cat test/e2e/page/self-polyfill.js \
    test/e2e/page/worklet-dsp-bundle.raw.js \
    test/e2e/page/worklet-processor-tail.js \
    > test/e2e/page/worklet-processor.js
rm -f test/e2e/page/worklet-dsp-bundle.raw.js

echo "wrote test/e2e/page/main-driver-bundle.js and test/e2e/page/worklet-processor.js"
