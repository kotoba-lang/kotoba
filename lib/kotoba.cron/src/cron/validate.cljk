(ns cron.validate
  "Structural validation of a parsed cron map (from cron.model/parse). Pure:
  returns a vector of problem maps so the caller decides how to surface them.

  Problem shape: {:cron/severity :error|:warn
                  :cron/code     keyword
                  :cron/id       keyword  ; which field
                  :cron/msg      string}

  `valid?` is true iff there are no :error-level problems (warnings are advisory)."
  (:require [cron.model :as m]))

(defn- problem [severity code id msg]
  {:cron/severity severity :cron/code code :cron/id id :cron/msg msg})

(defn- check-range!
  "Conj an :error if any value in `val-set` falls outside [lo, hi]."
  [ps field val-set lo hi label]
  (let [bad (filter #(or (< % lo) (> % hi)) val-set)]
    (when (seq bad)
      (conj! ps (problem :error :field/out-of-range field
                         (str label " values must be in " lo ".." hi
                              "; out-of-range: " (vec (sort bad))))))))

(defn- check-empty!
  "Conj an :error if `val-set` is empty (produced by an unsatisfiable step)."
  [ps field val-set label]
  (when (empty? val-set)
    (conj! ps (problem :error :field/empty field
                       (str label " resolved to an empty set")))))

(defn problems
  "Return a vector of validation problems for a parsed cron map."
  [cron]
  (let [ps (transient [])]
    ;; range checks
    (check-range! ps :cron/minute (:cron/minute cron)  0  59 "minute")
    (check-range! ps :cron/hour   (:cron/hour   cron)  0  23 "hour")
    (check-range! ps :cron/dom    (:cron/dom    cron)  1  31 "dom")
    (check-range! ps :cron/month  (:cron/month  cron)  1  12 "month")
    (check-range! ps :cron/dow    (:cron/dow    cron)  0   6 "dow")
    ;; empty-set checks (e.g. */0 would throw at parse; this covers edge cases)
    (check-empty! ps :cron/minute (:cron/minute cron) "minute")
    (check-empty! ps :cron/hour   (:cron/hour   cron) "hour")
    (check-empty! ps :cron/dom    (:cron/dom    cron) "dom")
    (check-empty! ps :cron/month  (:cron/month  cron) "month")
    (check-empty! ps :cron/dow    (:cron/dow    cron) "dow")
    (persistent! ps)))

(defn errors
  "Return only the :error-severity problems."
  [cron]
  (filterv #(= :error (:cron/severity %)) (problems cron)))

(defn valid?
  "True iff the parsed cron map has no :error-level structural problems."
  [cron]
  (empty? (errors cron)))
