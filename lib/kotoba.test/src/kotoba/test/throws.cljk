(ns kotoba.test.throws
  "throws? -- addressed on its own.

  Split out of kotoba.lang.test on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  (:require [kotoba.lang.spec :as spec])
  #?(:clj  (:require [kotoba.lang.spec :as spec])
     :cljs (:require [kotoba.lang.spec :as spec])))

(defn throws?
  "True iff `f` throws. Optionally matches `pred` against the ex-data/Message."
  ([f] (try (f) false (catch #?(:clj Throwable :cljs :default) _ true)))
  ([f pred] (try (f) false
                 (catch #?(:clj Throwable :cljs :default) e
                   (pred e)))))
