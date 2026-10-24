(ns faceid.ports)

(defprotocol IFaceID
  (attest! [port request]))

(defprotocol IChallengeStore
  (consume-challenge! [store challenge-id]
    "Atomically consume challenge-id. Return true only the first time."))

(defprotocol IAttestationStore
  (put-attestation! [store attestation])
  (attestations-for-device [store device-id]))

(defn memory-challenge-store
  ([] (memory-challenge-store #{}))
  ([used]
   (let [state (atom (set used))]
     (reify IChallengeStore
       (consume-challenge! [_ challenge-id]
         (let [accepted? (atom false)]
           (swap! state
                  (fn [s]
                    (if (contains? s challenge-id)
                      s
                      (do (reset! accepted? true)
                          (conj s challenge-id)))))
           @accepted?))))))

(defn memory-attestation-store []
  (let [state (atom {})]
    (reify IAttestationStore
      (put-attestation! [_ attestation]
        (swap! state update (:faceid/device-id attestation) (fnil conj []) attestation)
        attestation)
      (attestations-for-device [_ device-id]
        (get @state device-id [])))))

(defn missing []
  (reify IFaceID
    (attest! [_ _]
      (throw (ex-info "IFaceID port not configured" {:port :faceid})))))
