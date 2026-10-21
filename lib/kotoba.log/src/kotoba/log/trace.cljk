(ns kotoba.log.trace
  "trace -- addressed on its own.

  Split out of kotoba.lang.log on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  (:require [kotoba.log.log :refer [log]])
)

(defn trace [logger message & [fields]] (log logger :trace message fields))
