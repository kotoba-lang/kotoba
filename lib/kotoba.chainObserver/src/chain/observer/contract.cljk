(ns chain.observer.contract
  "Fail-closed cross-chain snapshot validation without flattening finality.")

(def schema "kotoba.chain.observation.v1")

(def families #{:bitcoin :evm :solana :cosmos :substrate :lightning})
(def trust-levels
  #{:fully-validated :light-client :local-rpc :remote-rpc :unverified})
(def capability-vocabulary
  #{:chain/identity :chain/health :chain/tip :chain/finalized-tip
    :account/read :history/read :events/subscribe})

(defn hex-quantity [value]
  (when-not (and (string? value)
                 (re-matches #"0x(0|[1-9a-fA-F][0-9a-fA-F]*)" value))
    (throw (ex-info "Invalid hexadecimal quantity."
                    {:type :chain.observer/invalid-response})))
  #?(:clj (bigint (java.math.BigInteger. (subs value 2) 16))
     :cljs (js/BigInt value)))

(defn- valid-tip? [tip]
  (or (nil? tip)
      (and (map? tip)
           (nat-int? (:height tip))
           (or (nil? (:hash tip)) (string? (:hash tip)))
           (keyword? (:finality tip)))))

(defn validate-snapshot
  [{:keys [family chain-id identity health sync tip finalized-tip
           capabilities trust] :as value}]
  (when-not (and (= schema (:schema value))
                 (contains? families family)
                 (string? chain-id) (re-matches #"[-a-z0-9]+:[-A-Za-z0-9._-]+"
                                                chain-id)
                 (map? identity) (map? health) (map? sync)
                 (valid-tip? tip) (valid-tip? finalized-tip)
                 (set? capabilities)
                 (every? capability-vocabulary capabilities)
                 (contains? trust-levels (:level trust)))
    (throw (ex-info "Invalid chain observation snapshot."
                    {:type :chain.observer/invalid-snapshot})))
  value)

(defn assert-expected!
  [label expected actual error-type]
  (when (and expected (not= expected actual))
    (throw (ex-info (str "Unexpected chain " label ".")
                    {:type error-type :expected expected :actual actual})))
  actual)

(defn ready?
  [{:keys [health sync tip]}]
  (and (= :ok (:status health))
       (false? (:syncing? sync))
       (nat-int? (:height tip))))

(defn same-tip? [left right]
  (and (= (get-in left [:tip :height]) (get-in right [:tip :height]))
       (= (get-in left [:tip :hash]) (get-in right [:tip :hash]))))

(defn reorg?
  [before after]
  (and (= (get-in before [:tip :height])
          (get-in after [:tip :height]))
       (not= (get-in before [:tip :hash])
             (get-in after [:tip :hash]))))
