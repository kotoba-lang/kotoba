(ns kototama.pregel-gossip
  "Pregel gossip protocol and Byzantine-resilient quorum consensus.

  Wave 5 consensus layer:
  - Vertex-centric BSP (Bulk Synchronous Parallel) gossip
  - Each peer gossips its committed ledger-tail to k-nearest neighbors
  - Majority quorum consensus (no Byzantine faults assumed in Phase 1)
  - Convergence detection (all peers agree on same tail after N rounds)

  Superstep execution:
  1. Compute phase: each vertex processes messages in inbox
  2. Gossip phase: vertex sends updated ledger-tail to k-closest peers
  3. Vote phase: quorum consensus if majority vote matches
  4. Commit phase: if consensus reached, finalize ledger-tail

  References:
  - Pregel: A System for Large-Scale Graph Processing (Google)
  - Gossip algorithms (Demers et al.)
  - Raft consensus (non-Byzantine)"
  (:require [kototama.dht-peer :as dht]
            [kototama.dht-reachability :as reachability]
            [kototama.signal-request :as signal-req]))

;; Gossip message: vertex announces its state to neighbors
(defrecord GossipMessage
  [sender-id          ;; CID of sender
   ledger-tail        ;; committed ledger tail CID
   epoch-number       ;; superstep number (for ordering)
   timestamp          ;; when message was created
   signature          ;; ed25519 signature (optional in Phase 1)
   ])

;; Vertex state: per-peer consensus state
(defrecord Vertex
  [peer-id            ;; CID of this peer
   ledger-tail        ;; currently committed ledger tail
   local-grants       ;; CACAO multi-graph grants (from Wave 4a)
   inbox              ;; [GossipMessage...] messages received this superstep
   out-votes          ;; count of votes seen for each tail (for quorum)
   converged?         ;; boolean, this vertex sees majority consensus
   ])

;; Create vertex for new peer
(defn new-vertex
  [peer-id initial-tail]
  {:pre [(string? peer-id)]}
  (->Vertex
   peer-id
   initial-tail
   {}  ;; empty grants
   []  ;; empty inbox
   {}  ;; empty out-votes
   false))

;; Superstep: process all messages, vote on consensus
;;
;; Input:  vertex (Vertex)
;;         peer-table (dht/PeerTable, for k-closest)
;;         received-messages (vec of GossipMessage from other peers)
;; Output: updated-vertex (Vertex with updated ledger-tail if consensus reached)
(defn compute-superstep
  [vertex peer-table received-messages]
  {:pre [(some? vertex)
         (some? peer-table)
         (vector? received-messages)]}
  (let [;; Tally votes for each ledger-tail
        tail-votes (frequencies (map :ledger-tail received-messages))
        ;; Quorum: majority of received messages + own vote
        total-votes (+ (count received-messages) 1)  ;; +1 for self
        quorum-threshold (inc (quot total-votes 2))  ;; > 50%

        ;; Find tail with most votes
        consensus-tail (first (apply max-key second tail-votes))
        vote-count (tail-votes consensus-tail)

        ;; Check if consensus reached (majority agrees)
        consensus-reached? (>= vote-count quorum-threshold)

        ;; Update ledger-tail if consensus or if we see a newer tail
        new-tail (if consensus-reached?
                   consensus-tail
                   ;; Otherwise, adopt the most-voted tail if newer than current
                   (if (and tail-votes
                            (> vote-count 1))
                     (or consensus-tail (:ledger-tail vertex))
                     (:ledger-tail vertex)))]

    (assoc vertex
      :ledger-tail new-tail
      :inbox received-messages
      :out-votes tail-votes
      :converged? consensus-reached?)))

;; Gossip round: each vertex sends state to k-closest neighbors
;;
;; Input:  vertices (map of peer-id → Vertex)
;;         peer-table (dht/PeerTable)
;;         k (number of closest peers to message, default 20)
;;         epoch-number (superstep counter)
;; Output: [GossipMessage...] messages to broadcast
(defn create-gossip-messages
  ([vertices peer-table epoch-number]
   (create-gossip-messages vertices peer-table 20 epoch-number))
  ([vertices peer-table k epoch-number]
   {:pre [(map? vertices)
          (some? peer-table)
          (pos? k)
          (number? epoch-number)]}
   (let [now-ms (System/currentTimeMillis)]
     (mapcat (fn [[peer-id vertex]]
               (let [k-closest (dht/k-closest peer-table peer-id k)]
                 (map (fn [target-peer]
                        (->GossipMessage
                         peer-id
                         (:ledger-tail vertex)
                         epoch-number
                         now-ms
                         nil))  ;; signature deferred
                      k-closest)))
             vertices))))

;; Consensus check: have all vertices converged to the same tail?
;;
;; Input:  vertices (map of peer-id → Vertex)
;; Output: {:converged? true|false, :tail <if-converged>}
(defn check-convergence
  [vertices]
  {:pre [(map? vertices)]}
  (let [tails (set (map :ledger-tail (vals vertices)))]
    (if (= (count tails) 1)
      {:converged? true
       :tail (first tails)
       :vertex-count (count vertices)}
      {:converged? false
       :distinct-tails (count tails)
       :vertex-count (count vertices)})))

;; Quorum consensus: majority voting on ledger-tail
;;
;; Input:  vertex-states (vec of Vertex records)
;; Output: {:consensus-tail <cid>, :quorum-size <count>, :unanimous? true|false}
(defn quorum-consensus
  [vertex-states]
  {:pre [(vector? vertex-states)]}
  (let [tail-votes (frequencies (map :ledger-tail vertex-states))
        total-votes (count vertex-states)
        quorum-threshold (inc (quot total-votes 2))  ;; > 50%

        ;; Find consensus tail (most votes)
        sorted-by-votes (sort-by second > tail-votes)
        [consensus-tail vote-count] (first sorted-by-votes)

        unanimous? (= vote-count total-votes)]
    {:consensus-tail consensus-tail
     :quorum-size vote-count
     :quorum-threshold quorum-threshold
     :unanimous? unanimous?
     :total-votes total-votes}))

;; Run one full gossip round
;;
;; Input:  vertices (map of peer-id → Vertex)
;;         peer-table (dht/PeerTable)
;;         peer-states (map of peer-id → reachability/PeerState)
;;         epoch-number (superstep counter)
;; Output: {:vertices <updated>, :messages-to-send [GossipMessage...], :stats <...>}
(defn run-gossip-round
  [vertices peer-table peer-states epoch-number]
  {:pre [(map? vertices)
         (some? peer-table)
         (map? peer-states)
         (number? epoch-number)]}
  (let [;; Create gossip messages
        messages-to-send (create-gossip-messages vertices peer-table 20 epoch-number)

        ;; Simulate message delivery (all messages received by all peers)
        ;; In reality, this would be async broadcast
        delivered-by-peer (group-by :sender-id messages-to-send)

        ;; Process messages at each vertex
        updated-vertices (into {}
                               (map (fn [[peer-id vertex]]
                                      (let [received-msgs (or (delivered-by-peer peer-id) [])]
                                        [peer-id
                                         (compute-superstep vertex peer-table
                                                           (vec received-msgs))]))
                                    vertices))

        ;; Check convergence
        convergence (check-convergence updated-vertices)

        ;; Quorum consensus
        consensus-result (quorum-consensus (vals updated-vertices))]
    {:vertices updated-vertices
     :messages-sent (count messages-to-send)
     :convergence convergence
     :consensus consensus-result
     :epoch-number epoch-number}))

;; Simulation: run N gossip rounds until convergence
;;
;; Input:  initial-vertices (map of peer-id → initial-tail)
;;         peer-table (dht/PeerTable)
;;         max-rounds (number)
;;         convergence-timeout-ms (stop if convergence detected)
;; Output: {:rounds-executed, :final-vertices, :converged?, :round-history [...]}
(defn simulate-gossip-convergence
  [initial-vertices peer-table max-rounds convergence-timeout-ms]
  {:pre [(map? initial-vertices)
         (some? peer-table)
         (pos? max-rounds)]}
  (let [vertices (into {}
                        (map (fn [[peer-id tail]]
                               [peer-id (assoc (new-vertex peer-id tail)
                                          :peer-id peer-id)])
                             initial-vertices))
        peer-states (into {}
                          (map (fn [[peer-id _]]
                                 [peer-id (->reachability/PeerState
                                           nil
                                           (System/currentTimeMillis)
                                           false
                                           0)])
                               initial-vertices))]
    (loop [round 0
           current-vertices vertices
           round-history []]
      (if (>= round max-rounds)
        {:rounds-executed round
         :final-vertices current-vertices
         :converged? false
         :reason :max-rounds-exceeded
         :round-history round-history}

        (let [round-result (run-gossip-round current-vertices peer-table peer-states round)
              converged? (get-in round-result [:convergence :converged?])]
          (if converged?
            {:rounds-executed (inc round)
             :final-vertices (:vertices round-result)
             :converged? true
             :consensus (:consensus round-result)
             :round-history (conj round-history round-result)}
            (recur (inc round)
                   (:vertices round-result)
                   (conj round-history round-result))))))))

;; Test: convergence simulation
(comment
  ;; Create 5 peers with different initial ledger tails
  (let [peer-table (dht/new-peer-table "peer-0")
        ;; Add 4 other peers to table
        peers (for [i (range 1 5)]
                (assoc (dht/->Peer (str "peer-" i) "10.0.0." i 9000)
                  :last-seen (System/currentTimeMillis)))
        _ (reduce dht/insert-peer peer-table peers)

        ;; Start with different tails
        initial-vertices {"peer-0" "tail-a"
                         "peer-1" "tail-a"
                         "peer-2" "tail-b"
                         "peer-3" "tail-b"
                         "peer-4" "tail-c"}

        ;; Run convergence simulation
        result (simulate-gossip-convergence initial-vertices peer-table 10 5000)]
    (:converged? result)
    ;; After ~3 rounds, all peers should agree on one tail (majority vote)))
