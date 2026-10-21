(ns kotoba.string.trim-text
  "trim-text -- one definition, addressed on its own.

  Split out of kotoba.lang.text on 2026-09-09. The unit here is the
  DEFINITION, not the library: this repo holds trim-text and names, in its
  deps.edn, exactly the definitions trim-text reaches. Nothing else."
  (:require [kotoba.string.ascii-ws :refer [ascii-ws?]]
            [kotoba.string.codepoints-of :refer [codepoints-of]]
            [kotoba.string.from-codepoints :refer [from-codepoints]]))

(defn trim-text
  "Oracle for the kernel's trim-text: strips ASCII whitespace from both ends."
  [s]
  (let [cps (vec (codepoints-of s))
        n (count cps)
        lead (loop [i 0] (if (and (< i n) (ascii-ws? (nth cps i))) (recur (inc i)) i))
        trail (loop [i (dec n)] (if (and (>= i 0) (ascii-ws? (nth cps i))) (recur (dec i)) i))]
    (if (> lead trail) "" (from-codepoints (subvec cps lead (inc trail))))))
