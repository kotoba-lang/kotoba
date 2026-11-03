(ns kami.eizo.compositor.e2e.entry
  "Browser bundle entry point for the real-pixel-data chroma-key + composite
  proof (test/e2e/). Pulls in both this repo's own compositing math
  (`kami.eizo.compositor.e2e.composite-proof`, which itself requires
  `kami.eizo.compositor.chroma-key` and `kami.eizo.compositor.blend`) and
  `org-w3-webcodecs`'s raw WebCodecs binding (`w3.webcodecs`), so a single
  `cljs.main -c` compile (scripts/build-e2e-bundle.sh) produces one bundle
  exposing both namespaces as browser globals for test/e2e/page/index.html
  to call into.

  With `:optimizations simple` (no renaming/inlining, same as
  org-w3-webcodecs's, kami-eizo-timeline's, and kami-eizo-grade's own E2E
  bundles), the functions below stay reachable from plain JS as
  `kami.eizo.compositor.e2e.entry.key_alpha_rgb255_js` and
  `kami.eizo.compositor.e2e.entry.composite_rgb255_js`."
  (:require [kami.eizo.compositor.e2e.composite-proof :as cp]
            [w3.webcodecs]))

(defn key-alpha-rgb255-js
  "`kami.eizo.compositor.e2e.composite-proof/key-alpha-rgb255` for a plain
  JS [r g b] triple, for index.html to call on a real decoded-frame pixel
  value. Returns a JS number (alpha in [0,1])."
  [r g b]
  (cp/key-alpha-rgb255 [r g b]))

(defn composite-rgb255-js
  "`kami.eizo.compositor.e2e.composite-proof/composite-rgb255` for plain JS
  [r g b] foreground/background triples and a JS alpha number, for
  index.html to call on real decoded-frame pixel values plus the
  browser-computed chroma-key alpha. Returns a plain JS array."
  [fr fg fb br bg bb alpha]
  (clj->js (cp/composite-rgb255 [fr fg fb] [br bg bb] alpha)))
