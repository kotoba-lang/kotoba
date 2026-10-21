(ns kotoba.log.debug
  "debug -- addressed on its own.

  Split out of kotoba.lang.log on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  (:require [kotoba.log.log :refer [log]])
)

(defn debug [logger message & [fields]] (log logger :debug message fields))
