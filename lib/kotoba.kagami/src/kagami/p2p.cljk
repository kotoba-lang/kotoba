(ns kagami.p2p
  "Phase 3b: gossip replication of the signed fleet head between fleet
  machines (ADR-2607160005). Wire-compatible with kotoba-lang/p2p's
  head-announce: a message is
    {:type :head-announce :graph :head-cid :seq :origin :from :fleet-head}
  where :fleet-head is the P3a signed head record (kagami.pin shape). Per
  kotoba-rad.announce's insight, a signed announce IS a sigref — no new
  signing primitive, we carry and verify the existing fleet head.

  This is the announce/verify/adopt subset (what a single-record head needs),
  not block-chasing (want-since/bitswap) — the fleet head is one record, not
  a chain of blocks to fetch. Full object-plane transfer (kotoba-git graphs)
  is a later slice. GitHub is thereby demoted to a mirror: machines learn
  each other's fleet head over this gossip, not by polling GitHub.

  Pure cljc; verify-fn injected. Trust set = the fleet keyring's roots +
  canonical allow (the dids permitted to announce a canonical fleet head)."
  (:require [kagami.pin :as pin]))

(defn head->announce
  "P3a signed head {:record :signature :signer} + node-id -> p2p announce msg."
  [{:keys [record signature signer]} node-id]
  {:type :head-announce
   :graph "fleet-db"
   :head-cid (:pin/value record)
   :seq (:pin/sequence record)
   :origin node-id :from node-id
   :fleet-head {:record record :signature signature :signer signer}})

(defn verify-announce
  "Is a received announce trustworthy enough to adopt?
  trust: #{did ...} allowed to announce a canonical fleet head.
  -> {:ok? bool :reasons [..]}"
  [{:keys [graph head-cid fleet-head] head-seq :seq}
   {:keys [trust verify-fn did->pubkey]}]
  (let [{:keys [record signature signer]} fleet-head
        reasons
        (cond-> []
          (not= "fleet-db" graph) (conj :wrong-graph)
          (not fleet-head) (conj :no-fleet-head)
          (and fleet-head (not= head-cid (:pin/value record))) (conj :head-cid-mismatch)
          (and fleet-head (not= head-seq (:pin/sequence record))) (conj :seq-mismatch)
          (not (contains? trust signer)) (conj :untrusted-signer)
          (not (try (verify-fn (did->pubkey signer) (pin/canonical-str record) signature)
                    (catch #?(:clj Exception :cljs :default) _ false)))
          (conj :bad-signature))]
    (if (seq reasons) {:ok? false :reasons (vec (distinct reasons))}
        {:ok? true :reasons []})))

(defn adopt
  "Fold a verified announce into a node's known head for fleet-db, iff its
  seq strictly advances (monotonic — same rule as pins). Returns node'.
  Unverified or non-advancing announces are ignored (no-op)."
  [node announce ctx]
  (let [cur (get-in node [:heads "fleet-db" :seq] -1)
        v (verify-announce announce ctx)]
    (if (and (:ok? v) (> (:seq announce) cur))
      (assoc-in node [:heads "fleet-db"]
                {:head-cid (:head-cid announce) :seq (:seq announce)
                 :fleet-head (:fleet-head announce) :from (:from announce)})
      node)))

(defn new-node [id] {:id id :heads {}})

(defn local-head [node] (get-in node [:heads "fleet-db"]))
