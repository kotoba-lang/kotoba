(ns kotobase.engine.conformance
  "Reusable semantic conformance checks for every engine implementation."
  (:require [kotobase.engine.completion :as completion]
            [kotobase.engine.contract :as engine]))

(defn- ensure! [check pred data]
  (when-not pred
    (throw (ex-info (str "engine conformance failed: " (name check))
                    {:type :kotobase.engine/conformance-failure
                     :check check :data data})))
  check)

(defn- bind-step [context step]
  (completion/then-result context step))

(defn verify
  "Run the minimum cross-engine semantic contract. Returns an immediate report
  for a synchronous engine or a Promise of the report for an async CLJS engine.
  Crash, provider-concurrency and performance gates remain separate suites."
  [eng]
  (let [database-id "conformance/db"
        tx1 {:database-id database-id :request-id "r1"
             :tx-data [[:db/add "alice" :person/name "Alice"]
                       [:db/add "alice" :person/role "admin"]]}
        tx2 {:database-id database-id :request-id "r2"
             :tx-data [[:db/retract "alice" :person/role "admin"]]}
        steps
        [(fn [c]
           (completion/then-result
            (engine/empty-state eng database-id)
            #(assoc c :s0 %)))
         (fn [{:keys [s0] :as c}]
           (completion/then-result
            (engine/transact eng s0 tx1)
            #(assoc c :r1 % :s1 (:state %))))
         (fn [{:keys [s1] :as c}]
           (completion/then-result
            (engine/open-snapshot eng s1)
            #(assoc c :snap1 %)))
         (fn [{:keys [snap1] :as c}]
           (completion/then-result
            (engine/scan eng snap1 ["alice" nil nil])
            #(assoc c :rows1 %)))
         (fn [{:keys [s1] :as c}]
           (completion/then-result
            (engine/transact eng s1 tx1)
            #(assoc c :replay %)))
         (fn [{:keys [s1] :as c}]
           (completion/then-result
            (engine/transact eng s1 tx2)
            #(assoc c :r2 % :s2 (:state %))))
         (fn [{:keys [s2] :as c}]
           (completion/then-result
            (engine/open-snapshot eng s2)
            #(assoc c :latest %)))
         (fn [{:keys [s2] :as c}]
           (completion/then-result
            (engine/open-snapshot eng s2 {:as-of 1})
            #(assoc c :old %)))
         (fn [{:keys [s2] :as c}]
           (completion/then-result
            (engine/open-snapshot eng s2 {:history true})
            #(assoc c :hist %)))
         (fn [{:keys [latest] :as c}]
           (completion/then-result
            (engine/scan eng latest ["alice" :person/role nil])
            #(assoc c :latest-role %)))
         (fn [{:keys [old] :as c}]
           (completion/then-result
            (engine/scan eng old ["alice" :person/role nil])
            #(assoc c :old-role %)))
         (fn [{:keys [hist] :as c}]
           (completion/then-result
            (engine/scan eng hist ["alice" nil nil])
            #(assoc c :history-rows %)))
         (fn [{:keys [latest] :as c}]
           (completion/then-result
            (engine/checkpoint eng latest)
            #(assoc c :checkpoint %)))
         (fn [{:keys [r1 replay rows1 latest-role old-role history-rows
                      checkpoint]}]
           (let [checks [(ensure! :profile (map? (engine/engine-profile eng)) {})
                         (ensure! :first-epoch (= 1 (get-in r1 [:receipt :epoch])) r1)
                         (ensure! :point-scan (= 2 (count rows1)) rows1)
                         (ensure! :replay (= :replayed (get-in replay [:receipt :status])) replay)
                         (ensure! :replay-no-advance (= 1 (get-in replay [:receipt :epoch])) replay)
                         (ensure! :retraction (empty? latest-role) latest-role)
                         (ensure! :as-of (= 1 (count old-role)) old-role)
                         (ensure! :history (= 3 (count history-rows)) history-rows)
                         (ensure! :logical-checkpoint-root
                                  (string? (:logical-checkpoint-root checkpoint))
                                  checkpoint)]]
             {:passed? true
              :engine (engine/engine-profile eng)
              :checks checks
              :checkpoint checkpoint}))]]
    (reduce bind-step {} steps)))
