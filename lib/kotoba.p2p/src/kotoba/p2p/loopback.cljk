(ns kotoba.p2p.loopback
  "In-memory reference transport for `kotoba.p2p.sync` — delivers effect
  envelopes `{:to peer-id :msg m}` to node state machines, breadth-first
  and deterministically, until the network is quiescent.

  This is the transport the protocol tests run on. A real transport
  (QUIC / WebRTC / WebTransport / HTTP long-poll) implements the same
  two duties — deliver `:effects`, feed incoming messages to
  `kotoba.p2p.sync/handle` — as host glue outside this repo."
  (:require [kotoba.p2p.sync :as sync]))

(defn network
  "A network of sync nodes: `nodes` maps peer-id -> node (see
  `kotoba.p2p.sync/new-node`)."
  [nodes]
  {:nodes nodes})

(defn run
  "Deliver `sends` (a seq of `{:to :msg}` envelopes) and every effect they
  transitively produce, until no messages remain. Messages to unknown
  peer-ids are dropped (a real transport's unreachable peer). Throws if
  `max-steps` (default 10000) deliveries don't reach quiescence — a
  protocol that can't go quiet is a bug, not a workload.
  Returns the final network."
  ([net sends] (run net sends 10000))
  ([net sends max-steps]
   (loop [net net inbox (vec sends) steps 0]
     (cond
       (empty? inbox) net

       (>= steps max-steps)
       (throw (ex-info "loopback: network did not go quiescent"
                       {:max-steps max-steps :backlog (count inbox)}))

       :else
       (let [{:keys [to msg]} (first inbox)
             rest-inbox (subvec inbox 1)]
         (if-let [node (get-in net [:nodes to])]
           (let [{node' :node effects :effects} (sync/handle node msg)]
             (recur (assoc-in net [:nodes to] node')
                    (into rest-inbox effects)
                    (inc steps)))
           (recur net rest-inbox (inc steps))))))))

(defn announce-and-run
  "Have `peer-id` announce its head for `graph`, then run to quiescence."
  [net peer-id graph]
  (let [{node' :node effects :effects}
        (sync/announce (get-in net [:nodes peer-id]) graph)]
    (run (assoc-in net [:nodes peer-id] node') effects)))
