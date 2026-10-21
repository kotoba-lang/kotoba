(ns kotoba.string.reverse-text
  "reverse-text -- one definition, addressed on its own.

  Split out of kotoba.lang.text on 2026-09-09. The unit here is the
  DEFINITION, not the library: this repo holds reverse-text and names, in its
  deps.edn, exactly the definitions reverse-text reaches. Nothing else."
  (:require [kotoba.string.codepoints-of :refer [codepoints-of]]
            [kotoba.string.from-codepoints :refer [from-codepoints]]))

(defn reverse-text
  "Oracle for the kernel's reverse-text: code-point-safe reversal (the kernel
  walks UTF-8 code points; this walks code points too, so astral characters
  survive -- unlike clojure.string/reverse on a surrogate pair). rseq, not
  rseq, not this namespace's own `reverse`, which is
  string-shaped and would see a vector."
  [s]
  (from-codepoints (vec (rseq (vec (codepoints-of s))))))
