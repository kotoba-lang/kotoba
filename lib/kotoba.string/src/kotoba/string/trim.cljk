(ns kotoba.string.trim
  "trim -- one definition, addressed on its own.

  Split out of kotoba.lang.text on 2026-09-09. The unit here is the
  DEFINITION, not the library: this repo holds trim and names, in its
  deps.edn, exactly the definitions trim reaches. Nothing else."
  (:require [kotoba.string.java-whitespace :refer [java-whitespace?]]))

(defn trim
  "Remove whitespace from both ends of `s`. See `java-whitespace?` for the
  class, which is Java's and is the same on every host here."
  [s]
  (let [s (str s)
        n (count s)]
    (loop [r n]
      (if (zero? r)
        ""
        (if (java-whitespace? (nth s (dec r)))
          (recur (dec r))
          (loop [l 0]
            (if (java-whitespace? (nth s l))
              (recur (inc l))
              (subs s l r))))))))
