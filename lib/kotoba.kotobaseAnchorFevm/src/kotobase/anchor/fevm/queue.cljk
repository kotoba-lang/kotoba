(ns kotobase.anchor.fevm.queue
  "Pure durable-job coordination for asynchronous FEVM checkpoint anchoring.

  This namespace performs no I/O. A host persists every returned record with
  the compare-and-set effect from `persist-plan`, and executes `work-effect`
  only after the claim CAS succeeds. This keeps FEVM, clocks, queues and
  durable stores outside the graph transaction path."
  (:require [kotoba.lang.text :as str]
            [kotobase.anchor.fevm :as fevm]))

(def job-version 1)

(def default-policy
  {:lease-ms 30000
   :poll-ms 15000
   :retry-base-ms 1000
   :retry-max-ms 300000
   :max-attempts 8})

(def ^:private active-statuses #{:pending :submitted :confirmed :failed})
(def ^:private all-statuses (conj active-statuses :finalized))
(def ^:private job-keys
  #{:job/version :idempotency-key :revision :attempt :next-at-ms :lease
    :anchor-state :submission-effect})
(def ^:private effect-keys
  #{:effect/type :chain :contract-address :idempotency-key :payload})
(def ^:private payload-keys
  #{:payload/version :database-id :epoch :logical-checkpoint-root :piece-cid})
(def ^:private state-keys
  (into payload-keys
        [:anchor-provider :status :tx-hash :height :block-hash :confirmations :reason]))

(defn- fail [message type data]
  (throw (ex-info message (assoc data :type type))))

(defn- nonblank-string? [value]
  (and (string? value) (not (str/blank? value))))

(defn- bounded-identifier? [value]
  (and (nonblank-string? value)
       (<= (count value) 256)
       (boolean (re-matches #"[A-Za-z0-9._:/=+-]+" value))))

(defn- nonnegative-integer? [value]
  (and (integer? value) (not (neg? value))))

(defn- positive-integer? [value]
  (and (integer? value) (pos? value)))

(defn- checked-time [now-ms]
  (when-not (nonnegative-integer? now-ms)
    (fail "FEVM queue time must be a non-negative integer"
          :kotobase.anchor/invalid-queue-time {:now-ms now-ms}))
  now-ms)

(defn- checked-policy [policy]
  (let [resolved (merge default-policy policy)]
    (when-not (and (= (set (keys default-policy)) (set (keys resolved)))
                   (positive-integer? (:lease-ms resolved))
                   (positive-integer? (:poll-ms resolved))
                   (positive-integer? (:retry-base-ms resolved))
                   (positive-integer? (:retry-max-ms resolved))
                   (<= (:retry-base-ms resolved) (:retry-max-ms resolved))
                   (positive-integer? (:max-attempts resolved)))
      (fail "invalid FEVM queue policy"
            :kotobase.anchor/invalid-queue-policy {:policy resolved}))
    resolved))

(defn- valid-lease? [lease]
  (or (nil? lease)
      (and (map? lease)
           (= #{:owner :until-ms} (set (keys lease)))
           (bounded-identifier? (:owner lease))
           (nonnegative-integer? (:until-ms lease)))))

(defn- state-evidence-valid? [state]
  (case (:status state)
    :pending true
    :submitted (bounded-identifier? (:tx-hash state))
    :confirmed (and (bounded-identifier? (:tx-hash state))
                    (nonnegative-integer? (:height state))
                    (bounded-identifier? (:block-hash state)))
    :finalized (and (bounded-identifier? (:tx-hash state))
                    (nonnegative-integer? (:height state))
                    (bounded-identifier? (:block-hash state))
                    (positive-integer? (:confirmations state)))
    :failed (or (keyword? (:reason state))
                (bounded-identifier? (:reason state)))
    false))

(defn- only-keys? [value allowed]
  (and (map? value) (every? allowed (keys value))))

(defn- checked-job [job]
  (let [state (:anchor-state job)
        effect (:submission-effect job)
        payload (:payload effect)
        logical-identity [:database-id :epoch :logical-checkpoint-root :piece-cid]]
    (when-not (and (map? job)
                   (= job-keys (set (keys job)))
                   (= job-version (:job/version job))
                   (bounded-identifier? (:idempotency-key job))
                   (nonnegative-integer? (:revision job))
                   (nonnegative-integer? (:attempt job))
                   (map? state)
                   (only-keys? state state-keys)
                   (contains? all-statuses (:status state))
                   (= :fevm (:anchor-provider state))
                   (state-evidence-valid? state)
                   (map? effect)
                   (= effect-keys (set (keys effect)))
                   (= :fevm/submit-checkpoint (:effect/type effect))
                   (keyword? (:chain effect))
                   (bounded-identifier? (:contract-address effect))
                   (map? payload)
                   (only-keys? payload payload-keys)
                   (every? #(contains? payload %)
                           [:payload/version :database-id :epoch
                            :logical-checkpoint-root])
                   (= (select-keys state logical-identity)
                      (select-keys payload logical-identity))
                   (= (:idempotency-key job) (:idempotency-key effect))
                   (valid-lease? (:lease job))
                   (if (= :finalized (:status state))
                     (nil? (:next-at-ms job))
                     (nonnegative-integer? (:next-at-ms job))))
      (fail "invalid FEVM durable anchor job"
            :kotobase.anchor/invalid-anchor-job {:job job}))
    job))

(defn new-job
  "Create a deterministic durable record. NOW-MS schedules work but is not
  included in the anchor idempotency key."
  [checkpoint config now-ms]
  (let [now-ms (checked-time now-ms)
        {:keys [state effect]} (fevm/submission-plan checkpoint config)]
    (checked-job
     {:job/version job-version
      :idempotency-key (:idempotency-key effect)
      :revision 0
      :attempt 0
      :next-at-ms now-ms
      :lease nil
      :anchor-state state
      :submission-effect effect})))

(defn enqueue-plan
  "Return a put-if-absent effect. Duplicate checkpoint submissions converge on
  one idempotency key; a host must never replace an existing record here."
  [checkpoint config now-ms]
  (let [record (new-job checkpoint config now-ms)]
    {:record record
     :effect {:effect/type :anchor-job/put-if-absent
              :key (:idempotency-key record)
              :record record}}))

(defn- lease-active? [job now-ms]
  (let [lease (:lease job)]
    (and lease (< now-ms (:until-ms lease)))))

(defn- retry-state [job policy]
  (if (= :failed (get-in job [:anchor-state :status]))
    (do
      (when (>= (:attempt job) (:max-attempts policy))
        (fail "FEVM anchor retry budget exhausted"
              :kotobase.anchor/retry-exhausted
              {:attempt (:attempt job)
               :max-attempts (:max-attempts policy)}))
      (assoc job :anchor-state (fevm/retry (:anchor-state job))))
    job))

(defn claim
  "Claim due work and bump its CAS revision. A host must persist this value
  before executing `work-effect`. Expired leases may be reclaimed."
  [job owner now-ms policy]
  (let [job (checked-job job)
        now-ms (checked-time now-ms)
        policy (checked-policy policy)
        status (get-in job [:anchor-state :status])]
    (when-not (bounded-identifier? owner)
      (fail "FEVM queue claim requires an owner"
            :kotobase.anchor/invalid-lease-owner {:owner owner}))
    (when (= :finalized status)
      (fail "finalized FEVM anchor job is terminal"
            :kotobase.anchor/terminal-anchor-job {}))
    (when (lease-active? job now-ms)
      (fail "FEVM anchor job already has an active lease"
            :kotobase.anchor/job-leased {:lease (:lease job)}))
    (when (< now-ms (:next-at-ms job))
      (fail "FEVM anchor job is not due"
            :kotobase.anchor/job-not-due {:next-at-ms (:next-at-ms job)}))
    (let [job (retry-state job policy)
          submitting? (= :pending (get-in job [:anchor-state :status]))]
      (checked-job
       (-> job
           (update :revision inc)
           (cond-> submitting? (update :attempt inc))
           (assoc :lease {:owner owner :until-ms (+ now-ms (:lease-ms policy))}))))))

(defn- checked-active-lease [job owner now-ms]
  (let [job (checked-job job)
        now-ms (checked-time now-ms)
        lease (:lease job)]
    (when-not (and (bounded-identifier? owner)
                   (= owner (:owner lease))
                   (< now-ms (:until-ms lease)))
      (fail "FEVM anchor worker does not hold an active lease"
            :kotobase.anchor/stale-anchor-worker
            {:owner owner :lease lease :now-ms now-ms}))
    job))

(defn work-effect
  "Return the one network effect authorized by an active claim."
  [job owner now-ms]
  (let [job (checked-active-lease job owner now-ms)
        state (:anchor-state job)
        status (:status state)]
    (cond
      (= :pending status)
      (assoc (:submission-effect job) :attempt (:attempt job))

      (#{:submitted :confirmed} status)
      {:effect/type :fevm/read-receipt
       :chain (get-in job [:submission-effect :chain])
       :transaction-hash (:tx-hash state)
       :expected-block-hash (:block-hash state)
       :idempotency-key (:idempotency-key job)}

      :else
      (fail "FEVM anchor state has no executable work"
            :kotobase.anchor/non-executable-anchor-state
            {:status status}))))

(defn- retry-delay-ms [attempt {:keys [retry-base-ms retry-max-ms]}]
  (loop [remaining (max 0 (dec attempt))
         delay retry-base-ms]
    (if (or (zero? remaining) (>= delay retry-max-ms))
      (min delay retry-max-ms)
      (recur (dec remaining) (min retry-max-ms (* 2 delay))))))

(defn- failure-reason? [reason]
  (or (keyword? reason) (bounded-identifier? reason)))

(defn- exact-result? [result expected-keys]
  (and (map? result) (= expected-keys (set (keys result)))))

(defn apply-result
  "Apply one bounded RPC observation, release the lease and schedule the next
  durable step. Results cannot skip lifecycle states or change identity."
  [job owner now-ms result policy]
  (let [job (checked-active-lease job owner now-ms)
        now-ms (checked-time now-ms)
        policy (checked-policy policy)
        state (:anchor-state job)
        status (:status state)
        result-type (:result/type result)
        [next-state next-at-ms]
        (case result-type
          :submitted
          (do
            (when-not (and (= :pending status)
                           (exact-result? result #{:result/type :tx-hash}))
              (fail "submitted result requires a pending anchor"
                    :kotobase.anchor/invalid-worker-result
                    {:status status :result result}))
            [(fevm/mark-submitted state {:tx-hash (:tx-hash result)})
             (+ now-ms (:poll-ms policy))])

          :confirmed
          (do
            (when-not (and (= :submitted status)
                           (exact-result? result #{:result/type :height :block-hash}))
              (fail "confirmed result requires a submitted anchor"
                    :kotobase.anchor/invalid-worker-result
                    {:status status :result result}))
            [(fevm/mark-confirmed state {:height (:height result)
                                         :block-hash (:block-hash result)})
             (+ now-ms (:poll-ms policy))])

          :finalized
          (do
            (when-not (and (= :confirmed status)
                           (exact-result? result #{:result/type :confirmations}))
              (fail "finalized result requires a confirmed anchor"
                    :kotobase.anchor/invalid-worker-result
                    {:status status :result result}))
            [(fevm/mark-finalized state {:confirmations (:confirmations result)}) nil])

          :not-final
          (do
            (when-not (and (#{:submitted :confirmed} status)
                           (exact-result? result #{:result/type}))
              (fail "not-final result requires an on-chain anchor"
                    :kotobase.anchor/invalid-worker-result
                    {:status status :result result}))
            [state (+ now-ms (:poll-ms policy))])

          :failed
          (do
            (when-not (and (active-statuses status)
                           (not= :failed status)
                           (exact-result? result #{:result/type :reason})
                           (failure-reason? (:reason result)))
              (fail "failed result requires an active anchor and bounded reason"
                    :kotobase.anchor/invalid-worker-result
                    {:status status :result result}))
            [(fevm/mark-failed state {:reason (:reason result)})
             (+ now-ms (retry-delay-ms (:attempt job) policy))])

          :reorged
          (do
            (when-not (and (#{:submitted :confirmed} status)
                           (exact-result? result #{:result/type}))
              (fail "reorg result requires an on-chain anchor"
                    :kotobase.anchor/invalid-worker-result
                    {:status status :result result}))
            [(fevm/mark-failed state {:reason :chain-reorg})
             (+ now-ms (retry-delay-ms (:attempt job) policy))])

          (fail "unknown FEVM worker result"
                :kotobase.anchor/invalid-worker-result {:result result}))]
    (checked-job
     (-> job
         (update :revision inc)
         (assoc :anchor-state next-state
                :next-at-ms next-at-ms
                :lease nil)))))

(defn persist-plan
  "Describe the CAS that must guard a claim or worker result. Immutable job
  identity and exactly-one revision advancement are enforced before I/O."
  [before after]
  (let [before (checked-job before)
        after (checked-job after)]
    (when-not (and (= (:idempotency-key before) (:idempotency-key after))
                   (= (:submission-effect before) (:submission-effect after))
                   (= (inc (:revision before)) (:revision after)))
      (fail "invalid FEVM anchor persistence transition"
            :kotobase.anchor/invalid-persistence-transition
            {:before-revision (:revision before)
             :after-revision (:revision after)}))
    {:effect/type :anchor-job/compare-and-set
     :key (:idempotency-key before)
     :expected-revision (:revision before)
     :record after}))
