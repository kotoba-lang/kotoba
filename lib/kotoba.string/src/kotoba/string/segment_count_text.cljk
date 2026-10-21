(ns kotoba.string.segment-count-text
  "segment-count-text -- one definition, addressed on its own.

  Split out of kotoba.lang.text on 2026-09-09. The unit here is the
  DEFINITION, not the library: this repo holds segment-count-text and names, in its
  deps.edn, exactly the definitions segment-count-text reaches. Nothing else."
  (:require [kotoba.string.split-literal :refer [split-literal]]))

(defn segment-count-text
  "Oracle for the kernel's segment-count-text: how many separator-delimited
  segments the text has (separators + 1). Matches
  clojure.string/split's count for non-regex separators."
  [s sep]
  (if (empty? sep)
    0
    (count (split-literal s sep))))
