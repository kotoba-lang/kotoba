(ns provider.incidence.soak
  "Resumable restart/partition stress harness for durable incidence stores."
  (:require [kotoba.lang.capability-values :as capabilities]
            [kotoba.lang.incidence :as incidence]
            [kotoba.lang.incidence-port :as port]
            [kotoba.lang.incidence-replication :as replication]
            [provider.incidence :as durable])
  (:import [java.nio.file Paths]))

(def dataspace "dataspace:incidence-soak/v1")
(def actor (incidence/typed-ref :did "did:key:z6MkIncidenceSoak"))
(def append-cap (capabilities/make-cap port/append-kind dataspace))

(defn- store [root name]
  (durable/open-store (.resolve root name) dataspace))

(defn- event [cycle parent]
  (incidence/assertion
   (incidence/incidence
    :soak/event {:organization #{actor}}
    (cond-> {:facts {:cycle cycle}}
      parent (assoc :parents #{parent})))))

(defn soak!
  "Run until TOTAL-CYCLES exist under ROOT; safe to invoke again after stop."
  [root total-cycles]
  (let [started (System/currentTimeMillis)
        stores (atom {:a (store root "a") :b (store root "b")
                      :c (store root "c")})
        existing (durable/entries (:a @stores))
        start (count existing)
        parent (atom (:incidence/cid (last (sort-by #(get-in % [:incidence/block
                                                                 :incidence/facts
                                                                 :cycle])
                                                    existing))))
        pending (atom {:b [] :c []})
        partitions (atom 0)
        restarts (atom 0)]
    (doseq [cycle (range start total-cycles)]
      (let [entry (event cycle @parent)
            deliver! (fn [node]
                       (doseq [candidate (conj (get @pending node) entry)]
                         (durable/append!
                          (node @stores)
                          {:dataspace dataspace :entry candidate
                           :capability append-cap}))
                       (swap! pending assoc node []))]
        (durable/append! (:a @stores)
                         {:dataspace dataspace :entry entry
                          :capability append-cap})
        (reset! parent (:incidence/cid entry))
        ;; Multi-cycle partitions accumulate a bounded backlog. B and C are
        ;; never partitioned together, so each event reaches one replica now.
        (let [partition-b? (< (mod cycle 23) 5)
              partition-c? (and (not partition-b?)
                                (<= 10 (mod cycle 31) 16))]
        (when (or partition-b? partition-c?) (swap! partitions inc))
          (if partition-b?
            (swap! pending update :b conj entry)
            (deliver! :b))
          (if partition-c?
            (swap! pending update :c conj entry)
            (deliver! :c))))
      (when (= 0 (mod (inc cycle) 13))
        (swap! restarts inc)
        (reset! stores {:a (store root "a") :b (store root "b")
                        :c (store root "c")})))
    ;; Heal every simulated partition before qualification.
    (doseq [node [:b :c]
            entry (get @pending node)]
      (durable/append! (node @stores)
                       {:dataspace dataspace :entry entry
                        :capability append-cap}))
    (let [expected (set (durable/entries (:a @stores)))
          recovered (into {}
                          (for [node [:b :c]
                                :let [replica (durable/recover (node @stores))]]
                            [node {:entries (count (:replica/blocks replica))
                                   :projection-ok?
                                   (:ok? (replication/projection replica))
                                   :same? (= expected
                                             (set (durable/entries
                                                   (node @stores))))}]))]
      {:soak/profile :provider-incidence/restart-partition-v1
       :soak/start-cycle start
       :soak/target-cycles total-cycles
       :soak/partitions @partitions
       :soak/restarts @restarts
       :soak/duration-ms (- (System/currentTimeMillis) started)
       :soak/recovered recovered
       :soak/passed? (every? #(and (:same? %) (:projection-ok? %))
                             (vals recovered))})))

(defn -main [& [root cycles]]
  (when-not (and root cycles (re-matches #"[1-9][0-9]*" cycles))
    (throw (ex-info "usage: ROOT TOTAL-CYCLES" {:problem :soak/arguments})))
  (prn (soak! (Paths/get root (make-array String 0)) (parse-long cycles))))
