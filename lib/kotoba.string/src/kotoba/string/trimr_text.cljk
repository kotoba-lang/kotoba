(ns kotoba.string.trimr-text
  "trimr-text -- one definition, addressed on its own.

  Split out of kotoba.lang.text on 2026-09-09. The unit here is the
  DEFINITION, not the library: this repo holds trimr-text and names, in its
  deps.edn, exactly the definitions trimr-text reaches. Nothing else."
  (:require [kotoba.string.ascii-ws :refer [ascii-ws?]]
            [kotoba.string.codepoints-of :refer [codepoints-of]]
            [kotoba.string.from-codepoints :refer [from-codepoints]]))

(defn trimr-text
  "Oracle for the kernel's trimr-text: strips ASCII whitespace from the right."
  [s]
  (let [cps (vec (codepoints-of s))
        n (count cps)
        trail (loop [i (dec n)] (if (and (>= i 0) (ascii-ws? (nth cps i))) (recur (dec i)) i))]
    (if (neg? trail) "" (from-codepoints (subvec cps 0 (inc trail))))))
