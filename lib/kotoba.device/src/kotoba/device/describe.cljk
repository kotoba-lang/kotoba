(ns kotoba.device.describe
  "describe -- addressed on its own.

  Split out of kotoba.lang.device on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  (:require [kotoba.lang.coll :as c]
            [kotoba.device.surface-effects :refer [surface-effects]]
            [kotoba.device.surface-schema :refer [surface-schema]])
)

(defn describe
  "Return a surface's schema (methods + effects), or nil if unknown."
  [s]
  (when-let [schema (surface-schema s)]
    (c/assoc-some (assoc schema :surface s)
                  :effects (get surface-effects s))))
