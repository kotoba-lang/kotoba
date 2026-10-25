(ns filecoin.node.tipset
  "A tipset: the set of blocks mined at one height on one parent set.

  Filecoin does not have a block per epoch. Every miner who wins the election
  for an epoch publishes a header, so an epoch's canonical state is produced
  by *all* of them together, and the tipset is that group. This is why
  `parent-state-root` lives in the header rather than a `state-root` — a
  header commits to the state after its parents, not after itself, because
  its own siblings are not known when it is signed.

  **The ordering is part of the identity.** A tipset key is the vector of its
  blocks' CIDs in ticket order, so a tipset assembled in the wrong order has
  a different key and names nothing. The order is by BLAKE2b-256 of the
  ticket's VRF proof, compared bytewise; identical tickets (which upstream
  logs as an anomaly rather than rejecting) fall back to comparing the
  **binary** CIDs. Comparing the base32 strings instead is a different order,
  because base32 is not order-preserving over the byte string it encodes.

  Construction rules, from `types.NewTipSet`: at least one block, every block
  has a ticket, all heights equal, and all parents equal — same count, same
  CIDs, same positions."
  ;; `parents` is the chain's word for this and shadowing core's is worth it,
  ;; but only said out loud — an implicit replacement is how a later edit in
  ;; here calls what it thinks is `clojure.core/parents` and gets a tipset
  ;; accessor.
  (:refer-clojure :exclude [parents])
  (:require [blake2.core :as blake2]
            [filecoin.node.block :as block]))

(defn- ->bytes [ints]
  #?(:clj (byte-array (map unchecked-byte ints))
     :cljs (let [out (js/Uint8Array. (count ints))]
             (dotimes [i (count ints)] (aset out i (nth ints i)))
             out)))

(defn- ->ints [data]
  (if (vector? data) data (mapv #(bit-and (int %) 0xff) (seq data))))

(defn ticket-digest
  "BLAKE2b-256 of a ticket's VRF proof — what `Ticket.Less` compares."
  [t]
  (->ints (blake2/blake2b-256 (->bytes (:vrf-proof t)))))

(defn- bytes<
  "Bytewise unsigned comparison, as Go's `bytes.Compare`."
  [a b]
  (loop [i 0]
    (cond (and (= i (count a)) (= i (count b))) false
          (= i (count a)) true
          (= i (count b)) false
          (not= (nth a i) (nth b i)) (< (nth a i) (nth b i))
          :else (recur (inc i)))))

(defn- block<
  "The tipset ordering: ticket digest, then binary CID."
  [a b]
  (let [da (ticket-digest (:ticket a))
        db (ticket-digest (:ticket b))]
    (if (= da db)
      (bytes< (block/cid-bytes a) (block/cid-bytes b))
      (bytes< da db))))

(defn tipset
  "Build a tipset from block headers, applying `types.NewTipSet`'s checks and
  sorting into ticket order."
  [headers]
  (let [hs (vec headers)]
    (when (empty? hs)
      (throw (ex-info "tipset: needs at least one block" {})))
    (doseq [h hs]
      (when-not (:ticket h)
        (throw (ex-info "tipset: block has no ticket" {:miner (:miner h)}))))
    (let [sorted (vec (sort block< hs))
          [head & rest-blocks] sorted]
      (doseq [b rest-blocks]
        (when-not (= (:height b) (:height head))
          (throw (ex-info "tipset: mismatched heights"
                          {:heights (mapv :height sorted)})))
        (when-not (= (:parents b) (:parents head))
          (throw (ex-info "tipset: mismatched parents" {}))))
      {:blocks sorted
       :cids (mapv block/cid sorted)
       :height (:height head)})))

(defn key-of
  "The tipset key: block CIDs in ticket order. This is what an RPC call means
  by `TipSetKey`."
  [ts]
  (:cids ts))

(defn height [ts] (:height ts))

(defn parents
  "The parent tipset's key, taken from the first block — every block in a
  tipset has the same parents, which `tipset` has already checked."
  [ts]
  (get-in ts [:blocks 0 :parents]))

(defn parent-state-root [ts] (get-in ts [:blocks 0 :parent-state-root]))
(defn parent-message-receipts [ts] (get-in ts [:blocks 0 :parent-message-receipts]))
(defn parent-weight [ts] (get-in ts [:blocks 0 :parent-weight]))
(defn parent-base-fee [ts] (get-in ts [:blocks 0 :parent-base-fee]))

(defn min-ticket-block
  "The block with the smallest ticket — the first in ticket order, and the
  one whose randomness the next epoch draws from."
  [ts]
  (first (:blocks ts)))

(defn min-timestamp
  "The earliest timestamp in the tipset. Not the first block's: ticket order
  and clock order are unrelated."
  [ts]
  (reduce min (map :timestamp (:blocks ts))))

(defn child-of?
  "Whether `ts` builds directly on `parent`: same CID set and strictly
  greater height. The height check is not redundant — null rounds mean a
  tipset's parent can be many epochs back, so equal heights with matching
  parents would be a fork, not a child."
  [ts parent]
  (and (= (set (parents ts)) (set (key-of parent)))
       (= (count (parents ts)) (count (key-of parent)))
       (> (height ts) (height parent))))
