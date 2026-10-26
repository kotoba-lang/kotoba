(ns kototama.dht-reachability
  "Peer reachability checks and health maintenance.

  Wave 5 DHT health layer:
  - PING/PONG messages (keep-alive, clock sync)
  - Peer freshness tracking (last-seen timestamp)
  - Stale peer removal (no PONG within timeout)
  - Periodic sweep (every 60s, check 20% of peers)

  This namespace manages peer state transitions:
  - :fresh (recently PONG'd) → :stale (no PONG for 5 min)
  - :stale → :unresponsive (no PONG for 30 min)
  - :unresponsive → evicted from table"
  (:require [kototama.dht-peer :as dht]))

(def ^:const PING-TIMEOUT-MS 5000)      ;; expect PONG within 5s
(def ^:const STALE-THRESHOLD-MS 300000) ;; 5 minutes
(def ^:const UNRESPONSIVE-THRESHOLD-MS 1800000) ;; 30 minutes

;; PING message
(defrecord Ping
  [sender-id          ;; CID of sender
   timestamp          ;; u64 ms since epoch
   nonce              ;; 32 random bytes, echoed in PONG
   ])

;; PONG message (response)
(defrecord Pong
  [sender-id          ;; CID of sender (who sent the PING)
   timestamp          ;; u64 ms since epoch
   nonce              ;; echo of nonce from PING
   ])

;; Peer state: extended with health tracking
(defrecord PeerState
  [peer                   ;; dht/Peer record
   last-pong-timestamp    ;; ms, when we last received PONG
   ping-in-flight?        ;; boolean, PING sent but PONG not yet received
   failure-count          ;; u32, consecutive PING timeouts
   ])

;; Peer health status
(defn peer-health
  [peer-state now-ms]
  {:pre [(some? peer-state)
         (number? now-ms)]}
  (let [time-since-pong (- now-ms (:last-pong-timestamp peer-state))
        failures (:failure-count peer-state)]
    (cond
      (>= time-since-pong UNRESPONSIVE-THRESHOLD-MS) :unresponsive
      (>= time-since-pong STALE-THRESHOLD-MS) :stale
      (>= failures 3) :unreliable
      :else :healthy)))

;; Send PING to peer
;;
;; Input:  sender-id (this peer's CID)
;;         target-peer (dht/Peer)
;; Output: Ping record (caller sends over network)
(defn create-ping
  [sender-id target-peer]
  {:pre [(string? sender-id)
         (some? target-peer)]}
  (let [;; 32 random bytes
        nonce (byte-array 32)
        _ (java.util.Random/nextBytes (int-array (map int nonce)))]
    (->Ping sender-id (System/currentTimeMillis) nonce)))

;; Handle PONG received
;;
;; Input:  table (dht/PeerTable)
;;         peer-states (map of peer-id → PeerState)
;;         pong (Pong record)
;; Output: updated-peer-states (map)
(defn handle-pong
  [peer-states pong]
  {:pre [(map? peer-states)
         (some? pong)]}
  (let [sender-id (:sender-id pong)
        now-ms (System/currentTimeMillis)]
    (if (contains? peer-states sender-id)
      (let [old-state (peer-states sender-id)]
        (assoc peer-states sender-id
               (assoc old-state
                 :last-pong-timestamp now-ms
                 :ping-in-flight? false
                 :failure-count 0)))
      peer-states)))

;; Handle PING timeout
;;
;; Input:  peer-states (map of peer-id → PeerState)
;;         peer-id (CID)
;; Output: updated-peer-states
(defn handle-ping-timeout
  [peer-states peer-id]
  {:pre [(map? peer-states)
         (string? peer-id)]}
  (if (contains? peer-states peer-id)
    (let [old-state (peer-states peer-id)]
      (assoc peer-states peer-id
             (-> old-state
                 (assoc :ping-in-flight? false)
                 (update :failure-count inc))))
    peer-states))

;; Periodic reachability sweep
;;
;; Run every 60 seconds to:
;; 1. PING stale peers (no PONG for 5 min)
;; 2. Remove unresponsive peers (no PONG for 30 min)
;; 3. Maintain peer table freshness
;;
;; Input:  table (dht/PeerTable)
;;         peer-states (map of peer-id → PeerState)
;;         sender-id (this peer's CID)
;;         now-ms (current timestamp)
;; Output: {:table <updated>, :peer-states <updated>, :pings-to-send [Ping...]}
(defn sweep-reachability
  [table peer-states sender-id now-ms]
  {:pre [(some? table)
         (map? peer-states)
         (string? sender-id)
         (number? now-ms)]}
  (let [all-peers (apply concat (map :peers (:buckets table)))
        ;; Partition peers by health
        health-by-peer (into {}
                             (map (fn [peer]
                                    [(:peer-id peer)
                                     (peer-health (get peer-states (:peer-id peer))
                                                 now-ms)])
                                  all-peers))

        ;; Peers to PING (stale, not already ping-in-flight)
        pings-needed (filter (fn [peer]
                               (and (= (health-by-peer (:peer-id peer)) :stale)
                                    (not (:ping-in-flight? (peer-states (:peer-id peer))))))
                             all-peers)

        ;; Peers to remove (unresponsive)
        peers-to-remove (filter (fn [peer]
                                  (= (health-by-peer (:peer-id peer)) :unresponsive))
                                all-peers)

        ;; Updated table (remove unresponsive)
        updated-table (reduce (fn [t peer]
                                (dht/remove-peer t (:peer-id peer)))
                              table
                              peers-to-remove)

        ;; Updated peer-states (mark PINGs as in-flight, remove unresponsive)
        updated-states (-> peer-states
                          (reduce (fn [states peer]
                                    (assoc states (:peer-id peer)
                                           (assoc (states (:peer-id peer))
                                             :ping-in-flight? true)))
                                  (into {}))
                          (reduce (fn [states peer]
                                    (dissoc states (:peer-id peer)))
                                  peers-to-remove))

        ;; Create PING messages
        pings-to-send (map (fn [peer]
                             (create-ping sender-id peer))
                           pings-needed)]
    {:table updated-table
     :peer-states updated-states
     :pings-to-send pings-to-send
     :removed-peer-count (count peers-to-remove)}))

;; Batch sweep: process multiple PONGs in one update
(defn handle-pongs-batch
  [peer-states pongs]
  {:pre [(map? peer-states)
         (vector? pongs)]}
  (reduce (fn [states pong]
            (handle-pong states pong))
          peer-states
          pongs))

;; Statistics for monitoring
(defn reachability-stats
  [peer-states]
  {:pre [(map? peer-states)]}
  (let [states (vals peer-states)
        now-ms (System/currentTimeMillis)
        health-counts (frequencies (map #(peer-health % now-ms) states))]
    {:total-peers (count states)
     :healthy (get health-counts :healthy 0)
     :stale (get health-counts :stale 0)
     :unreliable (get health-counts :unreliable 0)
     :unresponsive (get health-counts :unresponsive 0)
     :pings-in-flight (count (filter :ping-in-flight? states))}))

;; Test: PONG handling
(comment
  (let [peer-id "peer-1"
        initial-state {peer-id (->PeerState
                                 (->dht/Peer peer-id "10.0.0.1" 9000
                                            (System/currentTimeMillis) false)
                                 0
                                 true
                                 0)}
        pong (->Pong "peer-1" (System/currentTimeMillis) (byte-array 32))
        updated (handle-pong initial-state pong)]
    ;; PONG updates last-pong-timestamp
    (> (get-in updated [peer-id :last-pong-timestamp]) 0)))
