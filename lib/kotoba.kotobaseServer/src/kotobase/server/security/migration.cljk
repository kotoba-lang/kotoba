(ns kotobase.server.security.migration
  "Offline full-graph re-encryption with logical-datom parity verification."
  (:require [kotobase-peer.core :as eng]))

(defn reencrypt-graph [source-get source-head source-profile target-profile]
  (let [blocks (atom {})
        target-put! (fn [cid bytes] (swap! blocks assoc cid bytes))
        target-get (fn [cid] (get @blocks cid))
        rows (fn [db] (set (eng/datoms db (constantly true))))]
    (-> (eng/hydrate-chain source-get source-head
                           (:blind-fn source-profile) (:decrypt-fn source-profile))
        (.then
         (fn [source-db]
           (-> (eng/snapshot! target-put! target-get source-db nil
                              (:blind-fn target-profile) (:encrypt-fn target-profile))
               (.then
                (fn [target-head]
                  (-> (eng/hydrate-chain target-get target-head
                                         (:blind-fn target-profile)
                                         (:decrypt-fn target-profile))
                      (.then
                       (fn [target-db]
                         (when-not (= (rows source-db) (rows target-db))
                           (throw (ex-info "re-encryption parity check failed"
                                           {:type :migration-parity-failed})))
                         {:source-head source-head :target-head target-head
                          :datom-count (count (rows source-db)) :blocks @blocks})))))))))))
