(ns kotoba.device.surface-cap
  "surface-cap -- addressed on its own.

  Split out of kotoba.lang.device on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  (:require [kotoba.device.surface-to-cap :refer [surface->cap]])
)

(defn surface-cap
  "Return the capability string for a device surface keyword (`:bluetooth` etc)."
  [s] (surface->cap s))
