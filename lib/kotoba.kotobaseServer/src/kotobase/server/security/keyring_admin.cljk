(ns kotobase.server.security.keyring-admin
  "Offline keyring creation, rotation, and retirement. Only wrapped envelopes
  are returned."
  (:require [kotobase.cacao :as cacao]
            [kotobase.server.security.keywrap :as keywrap]))

(defn- random-key []
  (let [bytes (js/Uint8Array. 32)]
    (.getRandomValues js/crypto bytes)
    (cacao/bytes->base64 bytes)))
(defn- entry [] {"aead" (random-key) "blind" (random-key)})

(defn create-wrapped-keyring [recipient-public-key-b64 tenant-id key-id]
  (when-not (seq key-id)
    (throw (ex-info "key id required" {:type :key-id-required})))
  (keywrap/wrap-keyring recipient-public-key-b64
                        {"active" key-id "keys" {key-id (entry)}} tenant-id))

(defn rotate-wrapped-keyring
  [recipient-private-key-b64 recipient-public-key-b64 envelope tenant-id new-key-id]
  (-> (keywrap/unwrap-keyring recipient-private-key-b64 envelope tenant-id)
      (.then (fn [keyring]
               (when (contains? (get keyring "keys") new-key-id)
                 (throw (ex-info "key id already exists" {:type :key-id-conflict})))
               (keywrap/wrap-keyring
                recipient-public-key-b64
                (-> keyring (assoc "active" new-key-id)
                    (assoc-in ["keys" new-key-id] (entry))) tenant-id)))))

(defn retire-wrapped-key
  [recipient-private-key-b64 recipient-public-key-b64 envelope tenant-id key-id]
  (-> (keywrap/unwrap-keyring recipient-private-key-b64 envelope tenant-id)
      (.then (fn [keyring]
               (when (= key-id (get keyring "active"))
                 (throw (ex-info "cannot retire active key"
                                 {:type :active-key-retirement})))
               (when-not (contains? (get keyring "keys") key-id)
                 (throw (ex-info "unknown key id" {:type :key-id-unknown})))
               (keywrap/wrap-keyring recipient-public-key-b64
                                     (update keyring "keys" dissoc key-id)
                                     tenant-id)))))
