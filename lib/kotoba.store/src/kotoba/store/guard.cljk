(ns kotoba.store.guard
  "guard -- addressed on its own.

  Split out of kotoba.lang.store on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  (:require [kotoba.lang.wit :as w])
)

(defn guard
  "Return the store if `cap` is allowed by the policy, else nil."
  [s cap]
  (when (w/allows? (:policy s) cap) s))
