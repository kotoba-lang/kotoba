(ns kotoba.scheduler.shape-job
  "shape-job -- addressed on its own.

  Split out of kotoba.lang.scheduler on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  (:require [kotoba.lang.coll :as c])
)

(defn shape-job [job]
  ;; normalize a job entry via coll/assoc-some so optional fields are dropped
  ;; when nil — the kind of map-shaping coll exists for.
  (c/assoc-some job :interval? (:interval? job)))
