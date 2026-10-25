(ns bitcoin.node.disk-utxo
  "Node-facing host for bitcoin-consensus's transactional SQLite UTXO store.

  It derives the next active height and parent from durable state, parses raw
  blocks, selects network deployment flags, and commits value/Script/undo
  changes atomically. Header synchronization and fork choice stay in the
  higher-level consensus host."
  (:require [bitcoin.consensus.block :as block]
            [bitcoin.consensus.chainstate :as chainstate]
            [bitcoin.consensus.codec :as codec]
            [bitcoin.consensus.script :as script]
            [bitcoin.consensus.sqlite-utxo :as sqlite]
            [kotobase.bitcoin.protocol :as header]))

(defrecord DiskUTXOHost [backend network verify-script])

(defn open
  [{:keys [path datasource network busy-timeout-ms verify-script]
    :or {busy-timeout-ms 5000}}]
  (when-not (contains? chainstate/consensus-parameters network)
    (codec/fail! :bitcoin.node/unsupported-consensus-network
                 "The embedded disk UTXO host has no consensus parameters for this network."
                 {:network network}))
  (->DiskUTXOHost
   (sqlite/open {:path path :datasource datasource :network network
                 :busy-timeout-ms busy-timeout-ms})
   network verify-script))

(defn status [host]
  (assoc (sqlite/status (:backend host))
         :backend :sqlite-utxo
         :persistent? true))

(defn lookup [host outpoint]
  (sqlite/lookup (:backend host) outpoint))

(defn integrity-check! [host]
  (sqlite/integrity-check! (:backend host)))

(defn- expected-parent [parsed height]
  (when (pos? height)
    (header/natural-hash->hex (get-in parsed [:header :prev-block]))))

(defn- connect-genesis! [host parsed]
  (let [initialized
        (chainstate/initialize
         (:network host) parsed (:verify-script host))
        hash (:active-tip initialized)
        node (get-in initialized [:nodes hash])
        view (sqlite/begin (:backend host))]
    (try
      (assoc
       (sqlite/commit-transition!
        view
        {:expected-tip nil :expected-height -1
         :new-tip hash :new-height 0 :detach []
         :attach [{:block-hash hash :parent-hash nil
                   :height 0 :previous-height -1
                   :undo (:undo node)}]})
       :backend :sqlite-utxo)
      (catch Throwable error
        (sqlite/rollback! view)
        (throw error)))))

(defn connect-block!
  "Validate and atomically connect one raw block to the durable active tip.

  For CSV-active history, supply `:parent-mtp` and a `:coin-mtp` function in
  options. These values must come from the independently validated header
  chain."
  ([host raw-block] (connect-block! host raw-block {}))
  ([host raw-block options]
   (let [parsed (block/parse raw-block)
         before (sqlite/status (:backend host))
         height (inc (:height before))
         block-hash (get-in parsed [:header :hash-hex])
         parent (expected-parent parsed height)
         parameters (get chainstate/consensus-parameters (:network host))
         csv-active? (>= height (:csv-height parameters))
         _ (when-not (= (:tip before) parent)
             (codec/fail! :bitcoin.node/disk-utxo-parent
                          "Raw block does not extend the durable UTXO tip."
                          {:expected (:tip before) :actual parent
                           :height height}))
         _ (when (and csv-active?
                      (or (nil? (:parent-mtp options))
                          (not (ifn? (:coin-mtp options)))))
             (codec/fail!
              :bitcoin.node/missing-sequence-lock-context
              "CSV-active disk validation requires parent and coin MTP."
              {:height height}))
         flags (chainstate/script-flags parameters height block-hash)
         verifier
         (or (:verify-script host)
             (fn [transaction input-index coin]
               (script/verify-input transaction input-index coin flags)))
         transition-options
         (merge
          {:sequence-locks? csv-active?
           :allow-bip30-overwrite?
           (contains? chainstate/bip30-repeat-blocks block-hash)
           :halving-interval (:halving-interval parameters)
           :sigop-cost-fn
           #(script/transaction-sigop-cost %1 %2 flags)}
          (select-keys options [:parent-mtp :coin-mtp]))]
     (if (zero? height)
       (connect-genesis! host parsed)
       (assoc
        (sqlite/connect-block!
         (:backend host) parsed
         {:block-hash block-hash :parent-hash parent
          :height height :previous-height (:height before)}
         verifier transition-options)
        :backend :sqlite-utxo)))))

(defn disconnect-tip!
  ([host] (disconnect-tip! host (:tip (sqlite/status (:backend host)))))
  ([host expected-block-hash]
   (when-not expected-block-hash
     (codec/fail! :bitcoin.node/disk-utxo-empty
                  "The disk UTXO store has no active tip." {}))
   (assoc (sqlite/disconnect-tip! (:backend host) expected-block-hash)
          :backend :sqlite-utxo)))

(defn import-assumeutxo!
  "Stream and authenticate a Core v2 snapshot into an empty disk UTXO store."
  ([host source header-at-height]
   (import-assumeutxo! host source header-at-height {}))
  ([host source header-at-height options]
   (sqlite/import-snapshot! (:backend host) source header-at-height options)))
