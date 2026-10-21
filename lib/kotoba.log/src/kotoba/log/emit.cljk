(ns kotoba.log.emit
  "emit -- addressed on its own.

  Split out of kotoba.lang.log on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  (:require [kotoba.lang.coll :as c]
            [kotoba.log.level-enabled :refer [level-enabled?]])
)

(defn emit
  [logger lvl message fields]
  (when (level-enabled? logger lvl)
    (let [rec (cond-> {:level lvl :message message}
                (:context logger) (assoc :fields (c/deep-merge (:context logger) (or fields {})))
                (:span-id logger)  (assoc :span-id (:span-id logger))
                (:clock logger)     (assoc :ts ((:clock logger))))]
      ((:sink logger) rec)
      rec)))
