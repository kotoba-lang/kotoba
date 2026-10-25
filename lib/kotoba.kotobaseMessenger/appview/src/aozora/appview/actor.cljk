(ns aozora.appview.actor
  "Read projections for app.aozora.actor.* records — actor-to-actor
  relationships (currently just block), as opposed to aozora.appview.convo's
  actor-to-conversation ones."
  (:require [aozora.appview.feed :as feed]))

(defn- block-records-by
  "app.aozora.actor.block records AUTHORED by `did` — filtered by the scan
  row's own author (:did, per aozora.pds.encode/record->entity*'s
  did-from-uri), not a claimed :value field. Same reasoning as
  aozora.appview.convo/preference-records-for: a block record only ever
  describes the AUTHOR's own relationship to blockedDid, self-sovereign by
  construction."
  [records did]
  (->> records
       (filter #(= "app.aozora.actor.block" (:collection %)))
       (filter #(= did (:did %)))
       (keep :value)
       (filter map?)))

(defn list-blocks
  "GET app.aozora.actor.listBlocks."
  [client db-name {:keys [did limit]}]
  (let [lim (max 1 (min (or limit 200) 500))]
    (if (or (nil? did) (= "" did))
      (js/Promise.resolve {:blocks []})
      (-> (feed/scan-yoro client db-name)
          (.then (fn [{:keys [records]}]
                   {:blocks (->> (block-records-by records did)
                                 (take lim)
                                 (mapv #(select-keys % [:blockedDid :createdAt])))}))))))

(defn blocked?
  "Promise<boolean> — has `blocker-did` blocked `blocked-did`? For write-side
  enforcement (aozora.pds.convo's createConvo/sendSealed) — a single narrow
  check, not a full listBlocks fetch, since the caller only needs a yes/no."
  [client db-name blocker-did blocked-did]
  (if (or (nil? blocker-did) (nil? blocked-did))
    (js/Promise.resolve false)
    (-> (feed/scan-yoro client db-name)
        (.then (fn [{:keys [records]}]
                 (boolean (some #(= blocked-did (:blockedDid %)) (block-records-by records blocker-did))))))))
