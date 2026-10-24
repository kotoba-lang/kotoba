(ns mining-pool.share
  "Share validation: rebuild the coinbase transaction + merkle root from a
  Stratum job (coinb1/coinb2/merkle_branch, per the mining.notify wire
  format) and a miner's extranonce2/ntime/nonce submission, then check the
  resulting header against both the pool's share target (always easier —
  accept/reject the share) and the network's block target (did this share
  also happen to solve a real block?)."
  (:require [btc-crypto.core :as btc]
            [btc-mining.core :as m]))

(defn- concat-bytes ^bytes [arrays]
  (let [total (reduce (fn [^long n ^bytes a] (+ n (alength a))) 0 arrays)
        out (byte-array total)]
    (loop [off 0 as arrays]
      (if (seq as)
        (let [^bytes a (first as)]
          (System/arraycopy a 0 out off (alength a))
          (recur (+ off (alength a)) (rest as)))
        out))))

(defn rebuild-coinbase-txid
  "The Stratum coinbase-reconstruction rule: coinbase tx bytes =
  coinb1 ++ extranonce1 ++ extranonce2 ++ coinb2. Returns its SHA256d txid
  (internal byte order)."
  ^bytes [^bytes coinb1 ^bytes extranonce1 ^bytes extranonce2 ^bytes coinb2]
  (btc/sha256d (concat-bytes [coinb1 extranonce1 extranonce2 coinb2])))

(defn rebuild-merkle-root
  "Fold `coinbase-txid` up through the job's merkle branch (each step:
  new-root = SHA256d(root ++ branch-hash), all internal byte order) — the
  Stratum client-side merkle-root reconstruction rule."
  ^bytes [^bytes coinbase-txid merkle-branch]
  (reduce (fn [^bytes root ^bytes branch-hash] (btc/sha256d (concat-bytes [root branch-hash])))
          coinbase-txid
          merkle-branch))

(defn validate-submit
  "`job` — {:version :prev-hash :bits(network) :coinb1 :coinb2
  :merkle-branch(seq of 32B hashes)}. `submission` — {:extranonce1
  :extranonce2 :ntime :nonce}. `share-bits` — the pool-assigned (easier)
  target for this miner. Returns {:accepted? bool :block? bool
  :header-hash bytes}."
  [{:keys [version prev-hash bits coinb1 coinb2 merkle-branch]}
   {:keys [extranonce1 extranonce2 ntime nonce]}
   share-bits]
  (let [coinbase-txid (rebuild-coinbase-txid coinb1 extranonce1 extranonce2 coinb2)
        merkle-root (rebuild-merkle-root coinbase-txid merkle-branch)
        header {:version version :prev-hash prev-hash :merkle-root merkle-root
                :time ntime :bits bits :nonce nonce}
        h (m/header-hash header)]
    {:accepted? (m/meets-target? h share-bits)
     :block? (m/meets-target? h bits)
     :header-hash h}))
