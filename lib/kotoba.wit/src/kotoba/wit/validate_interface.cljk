(ns kotoba.wit.validate-interface
  "validate-interface -- addressed on its own.

  Split out of kotoba.lang.wit on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  (:require [kotoba.wit.interface :refer [interface?]]
            [kotoba.wit.problem :refer [problem]]
            [kotoba.wit.validate-function :refer [validate-function]]))

(defn validate-interface
  "Return a seq of problem maps for `iface`. Empty seq means valid."
  [iface]
  (cond
    (not (interface? iface))
    (list (problem [] iface :wit/not-an-interface))

    :else
    (let [fns  (:wit/functions iface)
          dups (for [[name freq] (frequencies (map :name fns))
                     :when (> freq 1)]
                 name)]
      (concat
       (mapcat (fn [i f] (validate-function f [:wit/functions i])) (range) fns)
       (when (seq dups)
         (list (problem [:wit/functions] dups :wit/duplicate-function-names)))))))
