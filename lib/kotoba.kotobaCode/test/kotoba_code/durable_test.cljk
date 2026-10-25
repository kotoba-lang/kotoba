(ns kotoba-code.durable-test
  (:require [clojure.test :refer [deftest is]]
            [kotoba-code.durable :as d]))

(deftest durable-loop-shape-is-edn-datom-friendly
  (let [l (d/new-loop "loop-1" {:session "s1" :budget {:tokens 100 :tool-calls 4}})
        t (d/next-tick l 1000)
        lease (d/acquire-lease l "worker-a" 1000 5000)
        released (d/release-lease l "worker-a" 1000)
        evt (d/event l t :tool-call {:name "run_tests"})
        gov (d/governor-event l t)]
    (is (= "loop-1" (:agent.loop/id l)))
    (is (= 1 (:agent.tick/seq t)))
    (is (d/lease-valid? lease 5999))
    (is (not (d/lease-valid? lease 6000)))
    (is (d/stale-lease? released 1000))
    (is (= :tool-call (:agent.event/type evt)))
    (is (= :continue (:agent.governor/decision gov)))
    (is (= [l t lease evt gov]
           (d/tx-data {:loop l :tick t :lease lease :events [evt] :governor gov})))))

(deftest budget-and-governor-are-tick-boundary-decisions
  (let [l0 (d/new-loop "loop-1" {:budget {:tokens 10 :tool-calls 2 :rounds 1}})
        t1 (d/next-tick l0 0)
        l1 (d/apply-tick l0 t1 {:tokens 7 :tool-calls 1} :done)
        t2 (d/next-tick l1 1)
        l2 (d/apply-tick l1 t2 {:tokens 3 :tool-calls 1} :done)]
    (is (= 1 (:agent.loop/tick-seq l1)))
    (is (= {:tokens 3 :tool-calls 1 :rounds 1} (:agent.loop/budget l1)))
    (is (= :continue (:agent.governor/decision (d/governor-decision l1))))
    (is (= :hold (:agent.governor/decision (d/governor-decision l2))))))

(deftest persist-uses-injected-datomic-api
  (let [seen (atom nil)
        api {:transact! (fn [conn tx] (reset! seen [conn tx]) {:tx-data tx})}
        l (d/new-loop "loop-1")
        t (d/next-tick l 0)]
    (is (= {:tx-data [l t]}
           (d/persist! api :conn {:loop l :tick t})))
    (is (= [:conn [l t]] @seen))))

(deftest supervisor-step-builds-a-complete-tick-transaction
  (let [l (d/new-loop "loop-1" {:budget {:tokens 10 :tool-calls 2 :rounds 1}})
        out (d/supervisor-step
             l
             {:now-ms 1000
              :owner "worker-a"
              :ttl-ms 5000
              :run-result {:status :done
                           :usage {:tokens 4 :tool-calls 1 :rounds 1}
                           :events [{:type :tool-call :payload {:name "run_tests"}}]}})]
    (is (= :hold (:decision out)) "round budget reaches zero after this tick")
    (is (= {:tokens 6 :tool-calls 1 :rounds 0} (get-in out [:loop :agent.loop/budget])))
    (is (= :done (get-in out [:tick :agent.tick/status])))
    (is (= "worker-a" (get-in out [:lease :agent.lease/owner])))
    (is (= 1000 (get-in out [:lease :agent.lease/expires-at])))
    (is (d/stale-lease? (:lease out) 1000))
    (is (= :tool-call (get-in out [:events 0 :agent.event/type])))
    (is (= (:tx-data out) (d/tx-data out)))))

(deftest supervisor-step-event-ids-are-unique-with-repeated-types
  (let [l (d/new-loop "loop-1")
        out (d/supervisor-step
             l
             {:now-ms 1000
              :owner "worker-a"
              :run-result {:events [{:type :tool-call :payload {:name "read_file"}}
                                    {:type :tool-call :payload {:name "run_tests"}}]}})
        ids (map :agent.event/id (:events out))]
    (is (= 2 (count (distinct ids))))
    (is (every? #(re-find #"/tool-call/\d+$" %) ids))))

(deftest lease-claim-step-records-pre-run-owner-without-spending-budget
  (let [l0 (d/new-loop "loop-1" {:budget {:tokens 10 :tool-calls 2 :rounds 1}})
        claimed (d/lease-claim-step l0 {:now-ms 1000
                                        :owner "worker-a"
                                        :ttl-ms 5000
                                        :task "do work"})]
    (is (= :lease-claimed (get-in claimed [:tick :agent.tick/status])))
    (is (= {:tokens 0 :tool-calls 0 :rounds 0}
           (get-in claimed [:tick :agent.tick/usage])))
    (is (= {:tokens 10 :tool-calls 2 :rounds 1}
           (get-in claimed [:loop :agent.loop/budget])))
    (is (= "worker-a" (get-in claimed [:lease :agent.lease/owner])))
    (is (= 6000 (get-in claimed [:lease :agent.lease/expires-at])))
    (is (= :lease (get-in claimed [:events 0 :agent.event/type])))
    (is (= {:owner "worker-a" :expires-at 6000 :task "do work"}
           (get-in claimed [:events 0 :agent.event/payload])))
    (is (= :continue (:decision claimed)))))

(deftest control-step-records-operator-state-changes
  (let [l0 (d/new-loop "loop-1")
        interrupted (d/control-step l0 {:now-ms 1000
                                        :owner "worker-a"
                                        :action :interrupt
                                        :reason "pause"})
        resumed (d/control-step (:loop interrupted) {:now-ms 2000
                                                     :owner "worker-a"
                                                     :action :resume})]
    (is (= :interrupted (get-in interrupted [:loop :agent.loop/status])))
    (is (= :require-human (:decision interrupted)))
    (is (= :control (get-in interrupted [:events 0 :agent.event/type])))
    (is (= {:action :interrupt :reason "pause" :effective? true}
           (get-in interrupted [:events 0 :agent.event/payload])))
    (is (= :active (get-in resumed [:loop :agent.loop/status])))
    (is (= :continue (:decision resumed)))
    (is (= 2 (get-in resumed [:tick :agent.tick/seq])))
    (is (= {:action :resume :reason nil :effective? true}
           (get-in resumed [:events 0 :agent.event/payload]))
        "regression: budget-exhausted? had a missing arg to <= (`(<= v)`
         instead of `(<= v 0)`), a single-arg <= call which Clojure always
         returns true for -- so a resume against a FRESH, full budget was
         unconditionally reported as :effective? false :blocked-by
         :budget-exhausted, even though the governor decision (:continue,
         asserted above) correctly said the budget was fine. This exact
         test already exercised the full-budget resume scenario but never
         checked the payload, which is why the bug went unnoticed")))

(deftest resume-does-not-hide-exhausted-budget
  (let [l0 (d/new-loop "loop-1" {:status :interrupted
                                 :budget {:tokens 10 :tool-calls 1 :rounds 0}})
        resumed (d/control-step l0 {:now-ms 1000
                                    :owner "worker-a"
                                    :action :resume
                                    :reason "try resume"})]
    (is (= :active (get-in resumed [:loop :agent.loop/status])))
    (is (= :hold (:decision resumed)))
    (is (= {:action :resume
            :reason "try resume"
            :effective? false
            :blocked-by :budget-exhausted}
           (get-in resumed [:events 0 :agent.event/payload])))))

(deftest refusal-step-preserves-loop-status-and-records-audit-event
  (let [l0 (d/new-loop "loop-1" {:status :stopped})
        refused (d/refusal-step l0 {:now-ms 1000
                                    :owner "worker-a"
                                    :reason :inactive-loop
                                    :task "try work"})]
    (is (= :stopped (get-in refused [:loop :agent.loop/status])))
    (is (= :refused (get-in refused [:tick :agent.tick/status])))
    (is (= :stop (:decision refused)))
    (is (= :refusal (get-in refused [:events 0 :agent.event/type])))
    (is (= {:reason :inactive-loop
            :status :stopped
            :task "try work"}
           (get-in refused [:events 0 :agent.event/payload])))
    (is (= (:tx-data refused) (d/tx-data refused)))))

(deftest reset-budget-step-reopens-held-loop-with-audit-event
  (let [l0 (d/new-loop "loop-1" {:budget {:tokens 0 :tool-calls 0 :rounds 0}})
        reset (d/reset-budget-step l0 {:now-ms 1000
                                       :owner "worker-a"
                                       :budget {:rounds 3}
                                       :reason "operator reset"})]
    (is (= :active (get-in reset [:loop :agent.loop/status])))
    (is (= {:tokens 12000 :tool-calls 40 :rounds 3}
           (get-in reset [:loop :agent.loop/budget])))
    (is (= :reset-budget (get-in reset [:tick :agent.tick/status])))
    (is (= :continue (:decision reset)))
    (is (= {:action :reset-budget
            :reason "operator reset"
            :effective? true
            :budget {:tokens 12000 :tool-calls 40 :rounds 3}}
           (get-in reset [:events 0 :agent.event/payload])))))
