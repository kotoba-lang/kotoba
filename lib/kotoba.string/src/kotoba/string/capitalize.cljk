(ns kotoba.string.capitalize
  "capitalize -- one definition, addressed on its own.

  Split out of kotoba.lang.text on 2026-09-09. The unit here is the
  DEFINITION, not the library: this repo holds capitalize and names, in its
  deps.edn, exactly the definitions capitalize reaches. Nothing else."
  (:require [kotoba.string.lower :refer [lower]]
            [kotoba.string.upper :refer [upper]]))

(defn capitalize
  "Upper-case the first character of `s` and lower-case the rest."
  [s]
  (let [s (str s)]
    (if (< (count s) 2)
      (upper s)
      (str (upper (subs s 0 1)) (lower (subs s 1))))))
