(ns kasane.svg
  "Thin adapter over org-w3-svg's svg.reader — this ns used to be a
   self-contained SVG XML reader; it's now a wrapper so kasane doesn't
   carry its own duplicate SVG parser. See ADR-2606272100 and the
   kotoba-lang reverse-domain media/graphics standards-substrate split
   (com-junkawasaki/root)."
  (:require [svg.reader :as reader]))

(def attrs reader/attrs)
(def parse-len reader/parse-len)
(def elements reader/elements)
(def root-attrs reader/root-attrs)
