(ns bim.spatial-benchmark
  "Repeatable large-model spatial/streaming performance gate."
  (:require [bim.spatial :as spatial]))

(defn- elapsed-ms [start]
  (/ (double (- (System/nanoTime) start)) 1.0e6))

(defn -main [& [element-count-arg]]
  (let [element-count (if element-count-arg (parse-long element-count-arg) 100000)
        _ (when-not (and element-count (pos? element-count))
            (throw (ex-info "benchmark element count must be positive"
                            {:value element-count-arg})))
        elements (mapv (fn [id]
                         (let [x (double (mod id 1000))
                               y (double (quot id 1000))]
                           {:id id :spatial/bounds
                            {:min [x y 0.0] :max [(+ x 0.8) (+ y 0.8) 3.0]}}))
                       (range element-count))
        build-start (System/nanoTime)
        index (spatial/build-index elements {:cell-size 10.0})
        build-ms (elapsed-ms build-start)
        query-start (System/nanoTime)
        report (spatial/query-report
                index {:min [100.0 20.0 -1.0] :max [109.9 29.9 4.0]})
        query-ms (elapsed-ms query-start)
        plan-start (System/nanoTime)
        plan (spatial/stream-plan
              index {:min [0.0 0.0 -1.0] :max [199.9 99.9 4.0]}
              [100.0 -100.0 50.0] 900.0 512 {:include-elements? false})
        plan-ms (elapsed-ms plan-start)
        result {:benchmark/elements element-count
                :benchmark/build-ms build-ms :benchmark/query-ms query-ms
                :benchmark/stream-plan-ms plan-ms
                :benchmark/candidates (:spatial/candidate-elements report)
                :benchmark/results (:spatial/returned-elements report)
                :benchmark/batches (count plan)
                :benchmark/pass? (and (< query-ms 250.0)
                                      (< (:spatial/candidate-elements report)
                                         (max 1000 (/ element-count 10))))}]
    (prn result)
    (when-not (:benchmark/pass? result)
      (throw (ex-info "large-model spatial performance gate failed" result)))))
