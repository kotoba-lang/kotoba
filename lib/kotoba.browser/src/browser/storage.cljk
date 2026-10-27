(ns browser.storage
  "Profile-scoped browser storage as pure data."
  (:require [browser.origin :as origin]
            [browser.profile :as profile]))

(defn empty-store
  []
  {:storage/data {}
   :storage/log []})

(defn storage-key
  [profile url k]
  (profile/storage-key profile (origin/origin url) k))

(defn put-value
  [store profile url k v]
  (let [sk (storage-key profile url k)]
    (-> store
        (assoc-in (into [:storage/data] sk) v)
        (update :storage/log conj {:op :storage/put
                                   :key sk
                                   :profile/id (:profile/id profile)
                                   :origin (origin/origin url)}))))

(defn get-value
  [store profile url k]
  (get-in store (into [:storage/data] (storage-key profile url k))))

(defn delete-value
  [store profile url k]
  (let [sk (storage-key profile url k)]
    (-> store
        (update :storage/data update-in sk (constantly nil))
        (update :storage/log conj {:op :storage/delete
                                   :key sk
                                   :profile/id (:profile/id profile)
                                   :origin (origin/origin url)}))))

(defn origin-entries
  [store profile url]
  (get-in store (into [:storage/data]
                      [(:profile/storage-partition profile)
                       (origin/origin url)])
          {}))
