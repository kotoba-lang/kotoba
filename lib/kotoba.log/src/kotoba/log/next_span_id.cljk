(ns kotoba.log.next-span-id
  "next-span-id -- addressed on its own.

  Split out of kotoba.lang.log on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  (:require [kotoba.log.id-counter :refer [id-counter]])
)

(defn next-span-id []
  ;; deterministic-ish id (no Math/random in pure lib); caller can override
  (swap! id-counter inc))
