(ns kotoba.store.store
  "store -- addressed on its own.

  Split out of kotoba.lang.store on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  (:require [kotoba.lang.coll :as c])
)

(defn store
  "Make a store from an `IFilesystem` (`fsb`) and a `wit` policy (`pol`, a set
  of granted capability strings). Options: `:prefix` (default `\"store/\"`)."
  ([fsb pol] (store fsb pol nil))
  ([fsb pol opts]
   ;; coll/deep-merge composes user opts over defaults — but deep-merge returns
   ;; nil when the right side is nil, so merge a normalized opts map first.
   (let [opts (or opts {})]
     (c/deep-merge {:fs fsb :policy pol :prefix "store/"} opts))))
