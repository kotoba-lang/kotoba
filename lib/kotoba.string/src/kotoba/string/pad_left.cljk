(ns kotoba.string.pad-left
  "pad-left -- one definition, addressed on its own.

  Split out of kotoba.lang.text on 2026-09-09. The unit here is the
  DEFINITION, not the library: this repo holds pad-left and names, in its
  deps.edn, exactly the definitions pad-left reaches. Nothing else."
  (:require [kotoba.string.join :refer [join]]
            [kotoba.string.pad :refer [pad]]))

(defn pad-left  [s width ch] (let [pad (max 0 (- width (count s)))] (str (join (repeat pad ch)) s)))
