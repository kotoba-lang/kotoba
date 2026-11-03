#!/usr/bin/env bash
# Compiles test/e2e/src/kami/eizo/timeline/e2e/entry.cljk (which pulls in
# both kami.eizo.timeline's portable timeline/frame query layer and
# org-w3-webcodecs's raw WebCodecs binding) ->
# test/e2e/page/render-proof-bundle.js for the browser render-proof E2E
# harness. Requires the Clojure CLI (JVM) -- build tool only (the
# ClojureScript compiler itself has no alternative; see
# org-w3-webcodecs/scripts/build-e2e-bundle.sh for the precedent this
# mirrors), not an app-runtime choice.
set -euo pipefail
cd "$(dirname "$0")/.."
kbb -M:e2e -m cljs.main --optimizations simple \
  --output-to test/e2e/page/render-proof-bundle.js \
  -c kami.eizo.timeline.e2e.entry
echo "wrote test/e2e/page/render-proof-bundle.js"
