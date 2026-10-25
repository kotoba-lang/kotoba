(ns bitcoin.consensus.sync
  "Bounded, pure multi-peer block-download scheduling.

  Networking is host-owned. This state machine prevents duplicate in-flight
  work, caps resource use, verifies responses against requested hashes, and
  deterministically requeues timed-out/disconnected work."
  (:require [bitcoin.consensus.codec :as codec]))

(def max-pending 100000)
(def max-inflight 128)
(def max-inflight-per-peer 16)
(def request-timeout-seconds 30)
(def ban-score 100)

(defn create [hashes]
  (let [pending (vec (distinct hashes))]
    (when (> (count pending) max-pending)
      (codec/fail! :bitcoin.consensus/sync-resource-limit
                   "Pending block queue exceeds its resource limit."
                   {:count (count pending) :limit max-pending}))
    {:pending pending :inflight {} :completed #{}
     :peers {}}))

(defn register-peer [state peer]
  (if (contains? (:peers state) peer)
    state
    (assoc-in state [:peers peer]
              {:inflight #{} :misbehavior 0 :connected? true})))

(defn eligible? [state peer]
  (let [{:keys [connected? misbehavior]} (get-in state [:peers peer])]
    (and connected? (< misbehavior ban-score))))

(defn- punish [state peer score]
  (update-in state [:peers peer :misbehavior] (fnil + 0) score))

(defn assign
  "Return [next-state requested-hashes], respecting per-peer/global bounds."
  ([state peer now] (assign state peer now max-inflight-per-peer))
  ([state peer now requested-limit]
   (when-not (contains? (:peers state) peer)
     (codec/fail! :bitcoin.consensus/unknown-peer
                  "Cannot assign work to an unknown peer." {:peer peer}))
   (if-not (eligible? state peer)
     [state []]
     (let [peer-count (count (get-in state [:peers peer :inflight]))
           capacity (max 0
                         (min requested-limit
                              (- max-inflight-per-peer peer-count)
                              (- max-inflight (count (:inflight state)))
                              (count (:pending state))))
           selected (vec (take capacity (:pending state)))
           remaining (vec (drop capacity (:pending state)))
           next-state
           (reduce
            (fn [result hash]
              (-> result
                  (assoc-in [:inflight hash]
                            {:peer peer :requested-at now})
                  (update-in [:peers peer :inflight] conj hash)))
            (assoc state :pending remaining) selected)]
       [next-state selected]))))

(defn process-block
  "Match a parsed block to one outstanding request. Returns a result map
  instead of throwing so a host can retain peer penalties."
  [state peer requested-hash parsed-block]
  (let [request (get-in state [:inflight requested-hash])
        actual (get-in parsed-block [:header :hash-hex])]
    (cond
      (nil? request)
      {:state (punish state peer 10)
       :accepted? false :error :unsolicited-block}

      (not= peer (:peer request))
      {:state (punish state peer 20)
       :accepted? false :error :wrong-peer}

      (not= requested-hash actual)
      {:state (punish state peer 100)
       :accepted? false :error :wrong-block}

      :else
      {:state
       (-> state
           (update :inflight dissoc requested-hash)
           (update-in [:peers peer :inflight] disj requested-hash)
           (update :completed conj requested-hash))
       :accepted? true :block parsed-block})))

(defn expire
  "Requeue timed-out requests and penalize each responsible peer."
  [state now]
  (let [expired
        (vec
         (keep (fn [[hash {:keys [peer requested-at]}]]
                 (when (>= (- now requested-at) request-timeout-seconds)
                   [hash peer]))
               (:inflight state)))
        requeued
        (reduce
         (fn [result [hash peer]]
           (-> result
               (update :inflight dissoc hash)
               (update-in [:peers peer :inflight] disj hash)
               (update :pending conj hash)))
         state expired)]
    (reduce #(punish %1 %2 5) requeued (distinct (map second expired)))))

(defn disconnect
  "Requeue a peer's outstanding requests immediately."
  [state peer]
  (let [hashes (get-in state [:peers peer :inflight] #{})]
    (-> (reduce
         (fn [result hash]
           (-> result
               (update :inflight dissoc hash)
               (update :pending conj hash)))
         state hashes)
        (assoc-in [:peers peer :inflight] #{})
        (assoc-in [:peers peer :connected?] false))))
