(ns kotoba.spec
  "Assembled from one repo per definition.

  This namespace holds no implementation. It re-exports the definitions
  that each live in their own repo, so a call site can require one name
  and a library can require only the definitions it actually uses.

  Value vars are not re-exported either: invalid. `(def x other/x)` copies, which is harmless for a function and makes
  with-redefs through this namespace a SILENT no-op for a value -- measured
  on kotoba.lang.edn, where three assertions passed against nothing at all.
  Require the repo that defines the value.
"
  (:refer-clojure :exclude [valid?])
  (:require [kotoba.spec.explain :as explain-ns]
            [kotoba.spec.explain-1 :as explain-1-ns]
            [kotoba.spec.valid :as valid-ns]
            [kotoba.spec.validate :as validate-ns]))

(def explain "See kotoba.spec.explain/explain." explain-ns/explain)
(def explain-1 "See kotoba.spec.explain-1/explain-1." explain-1-ns/explain-1)
(def valid? "See kotoba.spec.valid/valid?." valid-ns/valid?)
(def validate "See kotoba.spec.validate/validate." validate-ns/validate)
