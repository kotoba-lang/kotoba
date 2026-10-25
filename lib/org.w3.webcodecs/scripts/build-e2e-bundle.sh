#!/usr/bin/env bash
# Compiles src/w3/webcodecs.cljk -> test/e2e/page/webcodecs-bundle.js for the
# browser E2E harness. Requires the Clojure CLI (JVM) — this is a BUILD-time
# tool only (the ClojureScript compiler itself runs on the JVM; there is no
# alternative), not an app-runtime choice. The compiled bundle is what
# actually runs in the browser page.
set -euo pipefail
cd "$(dirname "$0")/.."
kbb -M -m cljs.main --optimizations simple \
  --output-to test/e2e/page/webcodecs-bundle.js \
  -c w3.webcodecs
echo "wrote test/e2e/page/webcodecs-bundle.js"
