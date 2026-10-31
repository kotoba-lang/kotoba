(ns kami.eizo.timeline.e2e.entry
  "Browser bundle entry point for the timeline render-proof E2E (test/e2e/).
  Pulls in both this repo's portable timeline query layer
  (`kami.eizo.timeline.e2e.render-proof`, which itself requires
  `kami.eizo.timeline` + `kami.eizo.timeline.timecode`) and
  `org-w3-webcodecs`'s raw WebCodecs binding (`w3.webcodecs`), so a single
  `cljs.main -c` compile (scripts/build-e2e-bundle.sh) produces one bundle
  exposing both namespaces as browser globals for
  test/e2e/page/index.html to call into."
  (:require [kami.eizo.timeline.e2e.render-proof]
            [w3.webcodecs]))
