(ns bitcoin.node.crash
  "Hard-process fault injection for the complete durable node transition."
  (:refer-clojure :exclude [run!])
  (:require [bitcoin.consensus.block :as block]
            [bitcoin.consensus.transaction :as transaction]
            [bitcoin.consensus.utxo :as utxo]
            [bitcoin.node.consensus-test :as fixture]
            [bitcoin.node.disk-consensus :as disk]
            [kotobase.bitcoin.protocol :as protocol])
  (:import [java.nio.file Files Path]
           [java.nio.file.attribute FileAttribute]
           [java.util.concurrent TimeUnit]))

(def schema "kotoba.bitcoin.node-crash-test.v1")

(def transition-faults
  [:transition/after-undo
   :transition/after-coins
   :transition/after-meta
   :transition/after-headers
   :transition/after-pending
   :transition/after-host
   :transition/after-prune
   :transition/before-commit
   :transition/after-commit])

(defn- bytes->hex [value]
  (apply str (map #(format "%02x" %) value)))

(defn- coinbase [height marker]
  (transaction/parse
   (transaction/serialize
    {:version 1
     :inputs [{:txid-natural (vec (repeat 32 0))
               :vout 0xffffffff
               :script-sig
               (conj (get-in (fixture/regtest-coinbase height)
                             [:inputs 0 :script-sig])
                     marker)
               :sequence 0xffffffff}]
     :outputs [{:value (utxo/block-subsidy height 150)
                :script-pubkey [81]}]
     :witnesses nil :locktime 0 :segwit? false})))

(defn- mine-block [parent height marker]
  (let [tx (coinbase height marker)
        template
        {:version 4
         :prev-block (get-in parent [:header :hash])
         :merkle-root (:txid-natural tx)
         :timestamp (inc (get-in parent [:header :timestamp]))
         :bits 0x207fffff}]
    (loop [nonce 0]
      (let [header-bytes
            (protocol/encode-block-header (assoc template :nonce nonce))
            decoded (protocol/decode-block-header header-bytes)]
        (if (protocol/hash-meets-target? (:hash decoded) (:bits decoded))
          (block/parse
           (vec (concat header-bytes [1] (:raw tx))))
          (recur (inc nonce)))))))

(defn- branch [parent length marker-base]
  (loop [height 1 parent parent result []]
    (if (> height length)
      result
      (let [next-block (mine-block parent height (+ marker-base height))]
        (recur (inc height) next-block (conj result next-block))))))

(defn- property! [condition message data]
  (when-not condition
    (throw
     (ex-info message
              (assoc data :type :bitcoin.node.crash/property)))))

(defn- crash-process! [path fault raw-block]
  (let [java
        (str (Path/of (System/getProperty "java.home")
                      (into-array String ["bin" "java"])))
        builder
        (doto
         (ProcessBuilder.
          (into-array
           String
           [java "-cp" (System/getProperty "java.class.path")
            "clojure.main" "-m" "bitcoin.node.sqlite-crash-worker"
            (str path) (subs (str fault) 1)
            (bytes->hex (block/serialize raw-block))]))
          (.redirectErrorStream true))
        process (.start builder)
        output
        (future
          (try
            (slurp (.getInputStream process))
            (catch java.io.IOException error
              (str "child output unavailable: " (.getMessage error)))))
        finished? (.waitFor process 60 TimeUnit/SECONDS)]
    (when-not finished?
      (.destroyForcibly process)
      (.waitFor process 5 TimeUnit/SECONDS))
    {:finished? finished?
     :exit (when finished? (.exitValue process))
     :output (deref output 10000 "child output drain timed out")}))

(defn- delete-store! [directory path]
  (doseq [target [path
                  (Path/of (str path ".background") (make-array String 0))
                  (Path/of (str path ".headers") (make-array String 0))
                  (Path/of (str path ".reindex") (make-array String 0))
                  (Path/of (str path ".reindex-pointer")
                           (make-array String 0))]
          suffix ["-shm" "-wal" ""]]
    (Files/deleteIfExists
     (Path/of (str target suffix) (make-array String 0))))
  (Files/deleteIfExists directory))

(defn- with-store [operation]
  (let [directory
        (Files/createTempDirectory
         "bitcoin-node-crash-" (make-array FileAttribute 0))
        path (.resolve directory "chainstate.sqlite")]
    (try
      (operation path)
      (finally (delete-store! directory path)))))

(defn- block-hash [value]
  (get-in value [:header :hash-hex]))

(defn- verify-node!
  [path expected-chain expected-pending fault scenario process]
  (property! (:finished? process)
             "Crash worker did not finish before its deadline."
             {:fault fault :scenario scenario :output (:output process)})
  (property! (= 91 (:exit process))
             "Crash worker did not stop at the requested fault point."
             {:fault fault :scenario scenario :process process})
  (let [node (disk/open {:path path :network :regtest})
        status (disk/consensus-status node)
        expected-tip (block-hash (peek expected-chain))]
    (property! (= (dec (count expected-chain)) (:height status))
               "Recovered node height is neither the old nor committed state."
               {:fault fault :scenario scenario :status status})
    (property! (= expected-tip (:best-block status))
               "Recovered node tip is inconsistent with commit visibility."
               {:fault fault :scenario scenario
                :expected expected-tip :status status})
    (property! (= expected-pending (:pending-blocks status))
               "Recovered pending branch rows split from the node transition."
               {:fault fault :scenario scenario
                :expected expected-pending :status status})
    (property! (= :ok (:integrity (disk/integrity-check! node)))
               "Recovered SQLite consensus database failed integrity audit."
               {:fault fault :scenario scenario :status status})
    (doseq [[height value] (map-indexed vector expected-chain)]
      (property!
       (= (block-hash value)
          (disk/active-block-hash-at-height node height))
       "Recovered active ancestry contains a partial transition."
       {:fault fault :scenario scenario :height height}))
    status))

(defn- linear-case! [fault]
  (with-store
    (fn [path]
      (let [genesis (block/parse (fixture/hex->bytes fixture/regtest-genesis))
            block-1 (mine-block genesis 1 1)
            block-2 (mine-block block-1 2 2)
            node
            (disk/open {:path path :network :regtest
                        :genesis-bytes
                        (fixture/hex->bytes fixture/regtest-genesis)})
            _ (disk/accept-block! node (block/serialize block-1) 2000000000)
            process (crash-process! path fault block-2)
            committed? (= fault :transition/after-commit)]
        (verify-node! path
                      (if committed? [genesis block-1 block-2]
                          [genesis block-1])
                      0 fault :linear process)))))

(defn- reorg-case! [fault]
  (with-store
    (fn [path]
      (let [genesis (block/parse (fixture/hex->bytes fixture/regtest-genesis))
            [main-1 main-2] (branch genesis 2 10)
            [side-1 side-2 side-3] (branch genesis 3 100)
            node
            (disk/open {:path path :network :regtest
                        :genesis-bytes
                        (fixture/hex->bytes fixture/regtest-genesis)})]
        (doseq [value [main-1 main-2 side-1 side-2]]
          (disk/accept-block! node (block/serialize value) 2000000000))
        (let [process (crash-process! path fault side-3)
              committed? (= fault :transition/after-commit)]
          (verify-node!
           path
           (if committed? [genesis side-1 side-2 side-3]
               [genesis main-1 main-2])
           (if committed? 0 2)
           fault :reorganization process))))))

(defn run! []
  (doseq [fault transition-faults]
    (linear-case! fault)
    (reorg-case! fault))
  {:schema schema :faults (count transition-faults)
   :scenarios (* 2 (count transition-faults))
   :result :passed})

(defn -main [& _]
  (try
    (println (pr-str (run!)))
    (finally
      (shutdown-agents))))
