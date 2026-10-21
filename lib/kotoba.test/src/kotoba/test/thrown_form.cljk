(ns kotoba.test.thrown-form
  "thrown-form? -- addressed on its own.

  Split out of kotoba.lang.test on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  (:require [kotoba.lang.spec :as spec])
  #?(:clj  (:require [kotoba.lang.spec :as spec])
     :cljs (:require [kotoba.lang.spec :as spec])))

(defn thrown-form?
  "True iff `expr` is the shape `(thrown? ExClass body...)`."
  [expr]
  (and (seq? expr) (>= (count expr) 2)
       (symbol? (first expr)) (= "thrown?" (name (first expr)))))
