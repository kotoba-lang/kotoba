(ns oidc.ports)

(defprotocol IOidc
  (verify-id-token! [port request token-ref])
  (userinfo! [port access-token-ref]))

(defprotocol INonceStore
  (consume-nonce! [store nonce]
    "Atomically consume an OIDC nonce. Return true only the first time."))

(defn memory-nonce-store
  ([] (memory-nonce-store #{}))
  ([used]
   (let [state (atom (set used))]
     (reify INonceStore
       (consume-nonce! [_ nonce]
         (let [accepted? (atom false)]
           (swap! state
                  (fn [s]
                    (if (contains? s nonce)
                      s
                      (do (reset! accepted? true)
                          (conj s nonce)))))
           @accepted?))))))
