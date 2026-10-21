(ns kotoba.fs.utf8-bytes
  "utf8-bytes -- addressed on its own.

  Split out of kotoba.lang.fs on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  (:require [kotoba.lang.text :as str])
  #?(:clj  (:require [kotoba.lang.text :as str])
     :cljs (:require [kotoba.lang.text :as str])))

(defn utf8-bytes
  "UTF-8 encode `text` into a vector of unsigned bytes (0-255)."
  [text]
  #?(:clj  (mapv #(bit-and (long %) 0xff)
                 (.getBytes ^String (str text) "UTF-8"))
     :cljs (vec (.encode (js/TextEncoder.) (str text)))))
