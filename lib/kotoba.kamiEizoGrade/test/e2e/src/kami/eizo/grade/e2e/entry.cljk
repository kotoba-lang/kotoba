(ns kami.eizo.grade.e2e.entry
  "Browser bundle entry point for the real-pixel-data grading proof
  (test/e2e/). Pulls in both this repo's own CDL math
  (`kami.eizo.grade.e2e.grade-proof`, which itself requires
  `kami.eizo.grade.cdl`) and `org-w3-webcodecs`'s raw WebCodecs binding
  (`w3.webcodecs`), so a single `cljs.main -c` compile
  (scripts/build-e2e-bundle.sh) produces one bundle exposing both
  namespaces as browser globals for test/e2e/page/index.html to call
  into.

  With `:optimizations simple` (no renaming/inlining, same as
  org-w3-webcodecs's and kami-eizo-timeline's own E2E bundles),
  `graded-rgb255-js` below stays reachable from plain JS as
  `kami.eizo.grade.e2e.entry.graded_rgb255_js`."
  (:require [kami.eizo.grade.e2e.grade-proof :as gp]
            [w3.webcodecs]))

(defn graded-rgb255-js
  "`kami.eizo.grade.e2e.grade-proof/grade-rgb255` as a plain JS array, for
  index.html to call on real decoded-frame pixel values."
  [r g b]
  (clj->js (gp/grade-rgb255 [r g b])))
