(ns kotoba.string.segment-text
  "segment-text -- one definition, addressed on its own.

  Split out of kotoba.lang.text on 2026-09-09. The unit here is the
  DEFINITION, not the library: this repo holds segment-text and names, in its
  deps.edn, exactly the definitions segment-text reaches. Nothing else."
  (:require [kotoba.string.split-literal :refer [split-literal]]))

(defn segment-text
  "Oracle for the kernel's segment-text: the nth (0-based) separator-delimited
  segment, or nil out of range (the kernel answers \"\" -- the divergence is
  the SENTINEL only; the segment contents agree). Literal separator, no
  regex."
  [s sep n]
  (if (or (empty? sep) (neg? n))
    nil
    (let [parts (split-literal s sep)]
      (when (< n (count parts))
        (nth parts n)))))
