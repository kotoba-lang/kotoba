(ns kotoba.async.can-put
  "can-put? -- addressed on its own.

  Split out of kotoba.lang.async on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  (:require [kotoba.async.closed :refer [closed?]])
)

(defn can-put?
  "True iff a put would be accepted right now. A closed channel never accepts.
  Fixed buffers refuse when full; dropping/sliding buffers always accept."
  [ch]
  (and (not (closed? ch))
       (if (= (:buf-type ch) :fixed)
         (< (count (:buffer ch)) (:cap ch))
         true)))
