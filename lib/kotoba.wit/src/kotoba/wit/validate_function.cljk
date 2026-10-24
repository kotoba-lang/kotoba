(ns kotoba.wit.validate-function
  "validate-function -- addressed on its own.

  Split out of kotoba.lang.wit on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  (:require [kotoba.wit.function :refer [function?]]
            [kotoba.wit.problem :refer [problem]]))

(defn validate-function [f path]
  (cond-> '()
    (not (function? f))
    (conj (problem (conj path :function) f :wit/not-a-function))
    (and (function? f) (some #(not (and (map? %) (string? (:name %)) (string? (:type %))))
                             (:params f)))
    (conj (problem (conj path :function :params) f :wit/bad-param))))
