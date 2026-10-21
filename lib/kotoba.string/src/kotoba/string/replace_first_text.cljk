(ns kotoba.string.replace-first-text
  "replace-first-text -- one definition, addressed on its own.

  Split out of kotoba.lang.text on 2026-09-09. The unit here is the
  DEFINITION, not the library: this repo holds replace-first-text and names, in its
  deps.edn, exactly the definitions replace-first-text reaches. Nothing else."
  (:require [kotoba.string.codepoints-of :refer [codepoints-of]]
            [kotoba.string.from-codepoints :refer [from-codepoints]]))

(defn replace-first-text
  "Oracle for the kernel's replace-first-text: replace the FIRST occurrence
  of the literal match. Not regex -- the kernel matches literals, so this
  diverges from clojure.string/replace (which takes a pattern)."
  [s match replacement]
  (let [cps (vec (codepoints-of s))
        mcps (vec (codepoints-of match))
        rcps (vec (codepoints-of replacement))
        n (count cps) m (count mcps)]
    (loop [i 0]
      (cond
        (> (+ i m) n) s
        (= m 0) s
        (= (subvec cps i (+ i m)) mcps)
        (from-codepoints (vec (concat (subvec cps 0 i) rcps (subvec cps (+ i m)))))
        :else (recur (inc i))))))
