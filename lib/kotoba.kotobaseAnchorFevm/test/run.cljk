(ns run
  (:require [kotobase.anchor.fevm.queue :as queue]))

(def checkpoint
  {:database-id "db/cljs"
   :epoch 7
   :logical-checkpoint-root "logical-root-7"
   :physical-root "must-not-cross-anchor-boundary"})

(def config
  {:chain :calibration
   :contract-address "t410f-checkpoint-contract"
   :digest-fn (constantly (apply str (repeat 64 "a")))})

(defn check [truth message]
  (when-not truth (throw (js/Error. message)))
  (println "ok -" message))

(defn error-type [f]
  (try
    (f)
    nil
    (catch :default error
      (:type (ex-data error)))))

(defn main []
  (let [policy {:lease-ms 10 :poll-ms 10 :retry-base-ms 5
                :retry-max-ms 20 :max-attempts 2}
        initial (queue/new-job checkpoint config 0)
        claimed (queue/claim initial "submitter" 0 policy)
        submitted (queue/apply-result claimed "submitter" 0
                                      {:result/type :submitted :tx-hash "tx-1"} policy)
        confirm-claim (queue/claim submitted "poller-1" 10 policy)
        confirmed (queue/apply-result confirm-claim "poller-1" 10
                                      {:result/type :confirmed :height 42
                                       :block-hash "block-a"} policy)
        final-claim (queue/claim confirmed "poller-2" 20 policy)
        finalized (queue/apply-result final-claim "poller-2" 20
                                      {:result/type :finalized :confirmations 900} policy)]
    (check (nil? (get-in initial [:submission-effect :payload :physical-root]))
           "physical root stays outside the anchor payload")
    (check (= :anchor-job/compare-and-set
              (:effect/type (queue/persist-plan initial claimed)))
           "claims require durable CAS")
    (check (= :fevm/submit-checkpoint
              (:effect/type (queue/work-effect claimed "submitter" 0)))
           "pending work emits a submission effect")
    (check (= :fevm/read-receipt
              (:effect/type (queue/work-effect confirm-claim "poller-1" 10)))
           "submitted work emits a receipt effect")
    (check (= :finalized (get-in finalized [:anchor-state :status]))
           "ordered evidence reaches finality")
    (check (= :kotobase.anchor/terminal-anchor-job
              (error-type #(queue/claim finalized "late-worker" 21 policy)))
           "finalized jobs are terminal")
    (check (= :kotobase.anchor/stale-anchor-worker
              (error-type #(queue/apply-result claimed "submitter" 10
                                               {:result/type :submitted
                                                :tx-hash "tx-stale"} policy)))
           "expired workers cannot publish")
    (check (= :kotobase.anchor/invalid-worker-result
              (error-type #(queue/apply-result claimed "submitter" 0
                                               {:result/type :finalized
                                                :confirmations 1} policy)))
           "lifecycle states cannot be skipped")
    (println "kotobase-anchor-fevm cljs: all green")))

(try
  (main)
  (catch :default error
    (js/console.error error)
    (js/process.exit 1)))
