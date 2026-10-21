(ns kotoba.store
  "Assembled from one repo per definition.

  This namespace holds no implementation. It re-exports the definitions
  that each live in their own repo, so a call site can require one name
  and a library can require only the definitions it actually uses.

  Value vars are not re-exported either: denied, read-cap, write-cap. `(def x other/x)` copies, which is harmless for a function and makes
  with-redefs through this namespace a SILENT no-op for a value -- measured
  on kotoba.lang.edn, where three assertions passed against nothing at all.
  Require the repo that defines the value.
"
  (:require [kotoba.store.delete :as delete-ns]
            [kotoba.store.exists :as exists-ns]
            [kotoba.store.get :as get-ns]
            [kotoba.store.put :as put-ns]
            [kotoba.store.store :as store-ns]
            [kotoba.store.with-policy :as with-policy-ns]))

(def delete "See kotoba.store.delete/delete." delete-ns/delete)
(def exists? "See kotoba.store.exists/exists?." exists-ns/exists?)
(def get "See kotoba.store.get/get." get-ns/get)
(def put "See kotoba.store.put/put." put-ns/put)
(def store "See kotoba.store.store/store." store-ns/store)
(def with-policy "See kotoba.store.with-policy/with-policy." with-policy-ns/with-policy)
