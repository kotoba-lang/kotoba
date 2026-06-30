(ns kotoba.wallet.tx
  "Canonical transaction intents. Hashes here are deterministic labels suitable
   for user approval binding; cryptographic hashing can be supplied by the host."
  (:require [clojure.string :as str]))

(defn normalize-hex [s]
  (let [s (or s "0x")]
    (if (str/starts-with? s "0x") (str/lower-case s) (str "0x" (str/lower-case s)))))

(defn normalize-address [s]
  (when s (str/lower-case s)))

(defn normalize-tx [chain-id {:keys [from to value data nonce gas gas-limit max-fee-per-gas
                                     max-priority-fee-per-gas origin kind account-id]}]
  {:chain-id chain-id
   :account-id account-id
   :from (normalize-address from)
   :to (normalize-address to)
   :value (str (or value "0"))
   :data (normalize-hex data)
   :nonce nonce
   :gas-limit (or gas-limit gas)
   :max-fee-per-gas max-fee-per-gas
   :max-priority-fee-per-gas max-priority-fee-per-gas
   :origin origin
   :kind (or kind :intent.kind/contract-call)})

(defn canonical-pairs [m]
  (->> m
       (remove (comp #{:hash :payload} key))
       (remove (comp nil? val))
       (sort-by (comp name key))
       (map (fn [[k v]] [(name k) (str v)]))))

(defn intent-hash
  "Stable, inspectable approval target. A host can additionally sign/hash this
   string with keccak/CID, but policy binds to these exact fields."
  [intent]
  (str "wallet-intent:v1:"
       (str/join "|" (map (fn [[k v]] (str k "=" v)) (canonical-pairs intent)))))

(defn tx->intent [id tx]
  (let [intent (assoc tx
                      :id id
                      :status :intent.status/pending-user)]
    (assoc intent :hash (intent-hash intent))))
