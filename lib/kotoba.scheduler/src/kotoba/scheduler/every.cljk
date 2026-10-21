(ns kotoba.scheduler.every
  "every -- addressed on its own.

  Split out of kotoba.lang.scheduler on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  (:require [kotoba.lang.time :as t]
            [kotoba.scheduler.shape-job :refer [shape-job]])
)

(defn every
  "Schedule a recurring job `id` that fires every `interval` (a time duration),
  starting at `:start` (defaults to now via the injected clock). `f` is called
  as `(f now)`. Options are passed as trailing key/value pairs, e.g.
  `(every s :b interval f :start instant)`. Scheduling does not touch
  :ready-queue — a job is only put onto the ready-queue by `tick`, once it
  actually fires (see tick's docstring)."
  ([sch id interval f & opts]
   (let [opts (apply hash-map opts)
         start (or (:start opts) (t/instant ((:clock sch))))
         job (shape-job {:id id :at start :fn f :interval? interval})]
     (update sch :jobs assoc id job))))
