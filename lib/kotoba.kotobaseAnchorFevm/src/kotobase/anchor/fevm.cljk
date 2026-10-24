(ns kotobase.anchor.fevm
  "Pure plans and lifecycle evidence for FEVM checkpoint anchoring."
  (:require [kotoba.lang.text :as str]
            [kotobase.engine.archive :as lifecycle]
            [kotobase.engine.canonical :as canonical]))

(def payload-version 1)

(defn checkpoint-payload
  [{:keys [database-id epoch logical-checkpoint-root piece-cid]}]
  (when-not (and (string? database-id) (not (str/blank? database-id))
                 (integer? epoch) (not (neg? epoch))
                 (string? logical-checkpoint-root)
                 (not (str/blank? logical-checkpoint-root))
                 (or (nil? piece-cid) (string? piece-cid)))
    (throw (ex-info "invalid FEVM checkpoint payload"
                    {:type :kotobase.anchor/invalid-payload})))
  (cond-> {:payload/version payload-version
           :database-id database-id
           :epoch epoch
           :logical-checkpoint-root logical-checkpoint-root}
    piece-cid (assoc :piece-cid piece-cid)))

(defn submission-plan
  "Create a deterministic, retry-safe host effect. DIGEST-FN receives the
  canonical payload string."
  [checkpoint {:keys [chain contract-address digest-fn]}]
  (when-not (and (keyword? chain) (string? contract-address)
                 (not (str/blank? contract-address)) (ifn? digest-fn))
    (throw (ex-info "FEVM submission requires chain, contract and digest"
                    {:type :kotobase.anchor/invalid-submission-config})))
  (let [payload (checkpoint-payload checkpoint)
        idempotency-key (digest-fn (canonical/canonical-string payload))
        request (lifecycle/anchor-request
                 (assoc payload :anchor-provider :fevm))]
    {:state request
     :effect {:effect/type :fevm/submit-checkpoint
              :chain chain
              :contract-address contract-address
              :idempotency-key idempotency-key
              :payload payload}}))

(defn call-message
  "Compatibility descriptor for the former Filecoin-native message boundary.
  Core no longer constructs Filecoin messages. An optional profile interprets
  this ordinary EVM call without putting cloud-filecoin on the default path."
  [{:keys [effect/type contract-address payload] :as effect}
   encode-calldata-fn message-options]
  (when-not (and (= :fevm/submit-checkpoint type) (ifn? encode-calldata-fn))
    (throw (ex-info "invalid FEVM checkpoint effect"
                    {:type :kotobase.anchor/invalid-effect :effect effect})))
  {:to contract-address
   :data (encode-calldata-fn payload)
   :options message-options})

(defn mark-submitted [state {:keys [tx-hash] :as evidence}]
  (when-not (and (string? tx-hash) (not (str/blank? tx-hash)))
    (throw (ex-info "submitted anchor requires tx hash"
                    {:type :kotobase.anchor/missing-transaction-hash})))
  (lifecycle/transition-anchor state :submitted evidence))

(defn mark-confirmed [state {:keys [height block-hash] :as evidence}]
  (when-not (and (integer? height) (not (neg? height))
                 (string? block-hash) (not (str/blank? block-hash)))
    (throw (ex-info "confirmed anchor requires chain height and block hash"
                    {:type :kotobase.anchor/missing-height})))
  (lifecycle/transition-anchor state :confirmed evidence))

(defn mark-finalized [state {:keys [confirmations] :as evidence}]
  (when-not (and (integer? confirmations) (pos? confirmations))
    (throw (ex-info "finalized anchor requires positive confirmations"
                    {:type :kotobase.anchor/missing-finality})))
  (lifecycle/transition-anchor state :finalized evidence))

(defn mark-failed [state evidence]
  (lifecycle/transition-anchor state :failed evidence))

(defn retry [state]
  ;; A reorg retry must not carry the orphaned receipt identity into the next
  ;; poll. The idempotency key lives on the durable job, not in this evidence.
  (-> (lifecycle/transition-anchor state :pending {})
      (dissoc :tx-hash :height :block-hash :confirmations :reason)))
