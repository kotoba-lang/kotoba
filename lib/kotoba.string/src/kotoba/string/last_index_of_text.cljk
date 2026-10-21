(ns kotoba.string.last-index-of-text
  "last-index-of-text -- one definition, addressed on its own.

  Split out of kotoba.lang.text on 2026-09-09. The unit here is the
  DEFINITION, not the library: this repo holds last-index-of-text and names, in its
  deps.edn, exactly the definitions last-index-of-text reaches. Nothing else."
  (:require [kotoba.string.codepoints-of :refer [codepoints-of]]
            [kotoba.string.utf8-byte-offsets :refer [utf8-byte-offsets]]))

(defn last-index-of-text
  "Oracle for the kernel's last-index-of-text: UTF-8 BYTE offset of the last
  occurrence, or -1 (clojure.string/last-index-of answers a UTF-16 index)."
  [s value]
  (let [cps (vec (codepoints-of s))
        needle (vec (codepoints-of value))
        n (count cps)
        m (count needle)
        offsets (utf8-byte-offsets cps)]
    (loop [i 0 best -1]
      (if (> i (- n m))
        best
        (recur (inc i)
               (if (= (subvec cps i (+ i m)) needle)
                 (nth offsets i)
                 best))))))
