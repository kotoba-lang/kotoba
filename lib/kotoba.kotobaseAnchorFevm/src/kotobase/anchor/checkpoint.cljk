(ns kotobase.anchor.checkpoint
  "Chain-neutral checkpoint anchor plans. Network adapters consume effects;
  graph transactions never wait for them."
  (:require [kotoba.lang.text :as str]
            [kotobase.engine.archive :as lifecycle]
            [kotobase.engine.canonical :as canonical]))

(def payload-version 1)
(def providers #{:transparency :evm})

(defn payload [{:keys [database-id epoch logical-checkpoint-root] :as checkpoint}]
  (when-not (and (string? database-id) (not (str/blank? database-id))
                 (integer? epoch) (not (neg? epoch))
                 (string? logical-checkpoint-root) (not (str/blank? logical-checkpoint-root)))
    (throw (ex-info "invalid checkpoint anchor payload"
                    {:type :kotobase.anchor/invalid-payload})))
  (select-keys (assoc checkpoint :payload/version payload-version)
               [:payload/version :database-id :epoch :logical-checkpoint-root]))

(defn submission-plan
  [checkpoint {:keys [provider network contract-address digest-fn]}]
  (when-not (and (providers provider) (ifn? digest-fn)
                 (or (= :transparency provider)
                     (and (string? network) (not (str/blank? network))
                          (string? contract-address) (not (str/blank? contract-address)))))
    (throw (ex-info "invalid checkpoint anchor provider configuration"
                    {:type :kotobase.anchor/invalid-submission-config})))
  (let [payload (payload checkpoint)
        idempotency-key (digest-fn (canonical/canonical-string payload))]
    {:state (if (= :evm provider)
              (lifecycle/anchor-request (assoc payload :anchor-provider :evm))
              (assoc payload :anchor-provider :transparency :status :pending))
     :effect (cond-> {:effect/type (if (= :evm provider)
                                    :evm/submit-checkpoint
                                    :checkpoint/append)
                      :provider provider
                      :idempotency-key idempotency-key
                      :payload payload}
               (= :evm provider) (assoc :network network :contract-address contract-address))}))
