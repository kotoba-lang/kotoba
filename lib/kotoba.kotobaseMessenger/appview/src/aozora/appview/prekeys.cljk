(ns aozora.appview.prekeys
  "Read projection for app.aozora.convo.prekeyBundle records.

  Same fold-then-filter shape as aozora.appview.convo (a full app.aozora.convo.*
  scan is already required for the messenger feed; the deterministic \"self\"
  rkey aozora.pds.prekeys/register-prekeys writes under means the fold has
  already collapsed re-registrations to a single current record per did, so
  no extra latest-wins logic is needed here)."
  (:require [aozora.appview.feed :as feed]))

(defn- bundle-records [records]
  (->> records
       (filter #(= "app.aozora.convo.prekeyBundle" (:collection %)))
       (map :value)
       (filter map?)))

(defn get-prekey-bundle
  "GET app.aozora.convo.getPrekeyBundle."
  [client db-name {:keys [did]}]
  (-> (feed/scan-yoro client db-name)
      (.then (fn [{:keys [records]}]
               (if-let [bundle (first (filter #(= did (:did %)) (bundle-records records)))]
                 (assoc (select-keys bundle [:did :identityKey :signedPreKey :signedPreKeySig :signedPreKeyId :oneTimePreKeys :updatedAt])
                        :found true)
                 {:found false})))))
