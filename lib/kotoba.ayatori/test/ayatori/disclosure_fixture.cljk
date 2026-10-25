(ns ayatori.disclosure-fixture
  "In-memory service fixture for the public recipient-delivery contract."
  (:require [kotobase.disclosure-grant :as d]
            [kotobase.execution-identity :as id]))

;; Explicit test-only signer and hybrid envelope metadata, not qualified crypto.
(def policy {:kotoba.security/crypto-policy-version 1
             :mode :hybrid-required :hybrid-epoch-floor 1})
(def context {:tenant "t" :owner "owner" :principal "alice"
              :recipient-key "alice-encryption-key" :executor "executor"
              :resource (d/ciphertext-cid [1 2 3]) :policy (id/value-cid :policy)
              :audience "key-service" :epoch 2 :now "2026-09-06T12:00:00Z"})

(defn sign [kind principal record]
  (assoc record :signature
         {:key/id principal :key/algorithm :fixture
          :signature/value (str principal ":" (d/signing-cid kind record))}))
(defn verify [{:keys [principal signature payload-cid]}]
  (and (= principal (:key/id signature))
       (= :fixture (:key/algorithm signature))
       (= (:signature/value signature) (str principal ":" payload-cid))))

(defn grant
  ([] (grant {}))
  ([overrides]
   (let [g (merge {:disclosure/version 1 :tenant "t" :owner "owner" :issuer "owner"
                   :recipient "alice" :recipient-key "alice-encryption-key"
                   :resource (:resource context) :policy (:policy context)
                   :operations #{:decrypt} :delegation-depth 2 :parent nil
                   :not-before "2026-09-06T11:00:00Z"
                   :expires-at "2026-09-06T13:00:00Z" :epoch 2}
                  overrides)
         envelope {:envelope/provider {:provider/id :fixture :provider/fips-validated false}
                   :envelope/algorithms [:x25519 :ml-kem-768 :aes-256-gcm]
                   :envelope/kem? true :envelope/hybrid? true :envelope/epoch 2
                   :envelope/binding (d/binding g) :sealed/ciphertext [10 20 30]}]
     {:grant (sign :disclosure-grant (:issuer g)
                   (assoc g :key-envelope-cid (id/value-cid envelope)))
      :envelope envelope})))

(defn request [g ctx]
  (sign :disclosure-request (:principal ctx)
        (merge (select-keys ctx [:tenant :principal :recipient-key :resource :audience :epoch])
               {:disclosure/version 1 :grant (id/value-cid g)
                :nonce "unique-request" :expires-at "2026-09-06T12:30:00Z"})))

(defn options
  ([] (options [(grant)] context))
  ([entries ctx]
   (let [chain (mapv :grant entries) journal (atom {}) spent (atom #{})]
     {:chain chain :request (request (peek chain) ctx) :context ctx
      :crypto-policy policy :key-envelope (:envelope (peek entries))
      :verify! verify :authorize! (constantly true)
      :consume-nonce! (fn [nonce]
                        (let [old @spent]
                          (and (not (contains? old nonce))
                               (compare-and-set! spent old (conj old nonce)))))
      :sign! (fn [{:keys [unsigned]}]
               (:signature (sign :disclosure-delivery "executor" unsigned)))
      :commit! (fn [r] (let [cid (id/value-cid r)]
                         (swap! journal assoc cid r)
                         {:receipt/durable? true :receipt/cid cid}))
      :read! (fn [cid] (get @journal cid))})))

