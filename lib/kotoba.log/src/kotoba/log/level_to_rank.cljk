(ns kotoba.log.level-to-rank
  "level->rank -- addressed on its own.

  Split out of kotoba.lang.log on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  (:require [kotoba.log.level-rank :refer [level-rank]])
)

(defn level->rank [lvl] (get level-rank lvl 99))
