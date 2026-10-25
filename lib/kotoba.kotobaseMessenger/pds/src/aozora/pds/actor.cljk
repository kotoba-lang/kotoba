(ns aozora.pds.actor
  "app.aozora.actor.* write handlers — actor-to-actor relationships
  (currently just block), as opposed to aozora.pds.convo's actor-to-
  conversation ones."
  (:require [kotoba.lang.text :as str]
            [aozora.pds.repo :as repo]))

(defn- non-blank [s] (when (and (string? s) (seq s)) s))
(defn- now-iso [] (.toISOString (js/Date.)))

(defn- require-auth [input]
  (or (non-blank (:_auth-did input))
      (non-blank (:repo input))))

(defn block
  "POST app.aozora.actor.block.

  Self-sovereign: one record per (caller, blockedDid) under the caller's own
  repo, deterministic rkey = blockedDid (re-blocking replaces, not
  accumulates)."
  [client db {:keys [blockedDid createdAt] :as input}]
  (let [did (require-auth input)]
    (if (or (nil? did) (str/blank? (or blockedDid "")))
      (js/Promise.resolve {:error "InvalidRequest"
                           :message "blockedDid and valid session required"})
      (-> (repo/create-record client db {:repo did
                                         :collection "app.aozora.actor.block"
                                         :rkey blockedDid
                                         :record {:did did :blockedDid blockedDid
                                                  :createdAt (or createdAt (now-iso))}})
          (.then (fn [r] (assoc r :did did :blockedDid blockedDid)))))))

(defn unblock
  "POST app.aozora.actor.unblock."
  [client db {:keys [blockedDid] :as input}]
  (let [did (require-auth input)]
    (if (or (nil? did) (str/blank? (or blockedDid "")))
      (js/Promise.resolve {:error "InvalidRequest"
                           :message "blockedDid and valid session required"})
      (-> (repo/delete-record client db {:repo did
                                         :collection "app.aozora.actor.block"
                                         :rkey blockedDid})
          (.then (fn [r] (assoc r :did did :blockedDid blockedDid)))))))
