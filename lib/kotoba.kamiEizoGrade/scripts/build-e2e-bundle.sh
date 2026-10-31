#!/usr/bin/env bash
# Compiles test/e2e/src/kami/eizo/grade/e2e/entry.cljk (which pulls in both
# this repo's own kami.eizo.grade.cdl primary-correction math and
# org-w3-webcodecs's raw WebCodecs binding) ->
# test/e2e/page/grade-proof-bundle.js for the browser real-pixel-data proof
# harness. Requires the Clojure CLI (JVM) -- build tool only (the
# ClojureScript compiler itself has no alternative; see
# org-w3-webcodecs/scripts/build-e2e-bundle.sh for the precedent this
# mirrors, also followed by kami-eizo-timeline/scripts/build-e2e-bundle.sh),
# not an app-runtime choice.
set -euo pipefail
cd "$(dirname "$0")/.."
kbb -M:e2e -m cljs.main --optimizations simple \
  --output-to test/e2e/page/grade-proof-bundle.js \
  -c kami.eizo.grade.e2e.entry
echo "wrote test/e2e/page/grade-proof-bundle.js"
