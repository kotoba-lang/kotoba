(ns kotoba.store.delete
  "delete -- addressed on its own.

  Split out of kotoba.lang.store on 2026-09-09 (ADR-2609091200). The unit
  here is the DEFINITION, and this repo's deps.edn names exactly the
  definitions it reaches -- nothing else.
"
  (:require [kotoba.lang.fs :as fs]
            [kotoba.store.denied :refer [denied]]
            [kotoba.store.guard :refer [guard]]
            [kotoba.store.key-to-path :refer [key->path]]
            [kotoba.store.write-cap :refer [write-cap]])
)

(defn delete
  "Delete `key`. Requires `store:write`. Returns `:kotoba.lang.store/denied` if not granted."
  [s key]
  (if-let [_ (guard s write-cap)]
    (do (fs/delete (:fs s) (key->path (:prefix s) key)) nil)
    denied))
