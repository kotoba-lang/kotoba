(ns num.deno-sampling-benchmark
  "Device-resident selection microbenchmark at a production-sized vocabulary."
  (:require [num.array :as arr]
            [num.deno-gpu :as gpu]))

(defn- percentile [values fraction]
  (let [values (vec (sort values))
        index (min (dec (count values))
                   (long (Math/floor (* fraction (count values)))))]
    (nth values index)))

(defn- timed [f]
  (let [started (.now js/performance)]
    (-> (js/Promise.resolve (f))
        (.then (fn [value]
                 {:value value :ms (- (.now js/performance) started)})))))

(defn- measure [iterations f]
  (-> (js/Promise.resolve (f))
      (.then
       (fn [_]
         (reduce (fn [promise _]
                   (.then promise
                          (fn [samples]
                            (-> (timed f)
                                (.then #(conj samples %))))))
                 (js/Promise.resolve []) (range iterations))))
      (.then
       (fn [samples]
         (let [times (mapv :ms samples)]
           {:token (:value (last samples))
            :iterations iterations
            :median-ms (percentile times 0.5)
            :min-ms (apply min times)
           :max-ms (apply max times)})))))

(defn- host-nucleus [logits temperature top-p random-value]
  (let [ranked (vec (sort-by (fn [[token logit]] [(- logit) token])
                             (map-indexed vector logits)))
        maximum (second (first ranked))
        weighted (mapv (fn [[token logit]]
                         [token (Math/exp (/ (- logit maximum) temperature))])
                       ranked)
        total (reduce + (map second weighted))
        nucleus (loop [remaining weighted cumulative 0.0 chosen []]
                  (let [[[_ weight :as entry] & more] remaining
                        cumulative' (+ cumulative weight)
                        chosen' (conj chosen entry)]
                    (if (or (>= (/ cumulative' total) top-p) (empty? more))
                      chosen'
                      (recur more cumulative' chosen'))))
        threshold (* random-value (reduce + (map second nucleus)))]
    (loop [[[token weight] & more] nucleus cumulative 0.0]
      (let [cumulative' (+ cumulative weight)]
        (if (or (> cumulative' threshold) (empty? more))
          token
          (recur more cumulative'))))))

(defn- run-benchmarks
  [request backend logits draft vocab iterations baseline nucleus-reference]
  (let [sample #(arr/sample-top-k-row
                 logits 0 {:top-k % :temperature 0.7
                           :top-p 0.9 :random-value 0.51})]
    (-> (measure iterations #(sample 8))
        (.then (fn [k8]
                 (-> (measure iterations #(sample 40))
                     (.then (fn [k40] [k8 k40])))))
        (.then (fn [[k8 k40]]
                 (-> (measure iterations #(sample 256))
                     (.then (fn [k256] [k8 k40 k256])))))
        (.then
         (fn [[k8 k40 k256]]
           (-> (measure iterations
                        #(arr/sample-softmax-row
                          logits 0 {:temperature 0.7 :random-value 0.51}))
               (.then #(vector k8 k40 k256 %)))))
        (.then
         (fn [[k8 k40 k256 full-softmax]]
           (-> (measure iterations
                        #(arr/sample-nucleus-row
                          logits 0 {:temperature 0.7 :top-p 0.9
                                    :random-value 0.51}))
               (.then #(vector k8 k40 k256 full-softmax %)))))
        (.then
         (fn [[k8 k40 k256 full-softmax nucleus]]
           (-> (measure iterations
                        #(arr/speculative-rejection-row
                          logits draft 0 17
                          {:temperature 0.7 :acceptance-random 0.9
                           :residual-random 0.51}))
               (.then #(vector k8 k40 k256 full-softmax nucleus %)))))
        (.then
         (fn [[k8 k40 k256 full-softmax nucleus speculative]]
           (-> (timed #(arr/speculative-rejection-rows
                        logits logits [17 18 19 20]
                        {:temperature 0.7 :acceptance-random 0.9
                         :residual-random 0.51}))
               (.then
                (fn [mtp]
                  (let [after (gpu/backend-stats backend)
                        result {:adapter (gpu/adapter-description request)
                                :vocab vocab
                                :top-k-8 k8 :top-k-40 k40 :top-k-256 k256
                                :full-softmax full-softmax
                                :nucleus nucleus
                                :nucleus-reference-token nucleus-reference
                                :speculative speculative
                                :mtp-prefix mtp
                                :readbacks (- (:selection-readbacks after 0)
                                              (:selection-readbacks baseline 0))
                                :readback-bytes
                                (- (:selection-readback-bytes after 0)
                                   (:selection-readback-bytes baseline 0))}]
                    (arr/release! logits)
                    (arr/release! draft)
                    (println (js/JSON.stringify (clj->js result)))
                    (when-not (and (= nucleus-reference (:token nucleus))
                                   (= 4 (get-in mtp [:value :drafted]))
                                   (= 4 (get-in mtp [:value :accepted]))
                                   (get-in mtp [:value :all-accepted?]))
                      (throw (ex-info "device selection verification failed"
                                      result))))))))))))

(defn -main [& _]
  (let [vocab 262144 iterations 3
        row-values (mapv #(Math/sin (* 0.017 %)) (range vocab))
        row-draft-values (mapv #(Math/cos (* 0.013 %)) (range vocab))
        values (vec (mapcat identity (repeat 4 row-values)))
        draft-values (vec (mapcat identity (repeat 4 row-draft-values)))
        nucleus-reference (host-nucleus row-values 0.7 0.9 0.51)]
    (-> (gpu/request-device)
        (.then (fn [request]
                 (let [backend (gpu/backend request)
                       logits (arr/from-vec backend values [4 vocab])
                       draft (arr/from-vec backend draft-values [4 vocab])]
                   (run-benchmarks request backend logits draft vocab iterations
                                   (gpu/backend-stats backend)
                                   nucleus-reference))))
        (.then (fn [_] (js/Deno.exit 0)))
        (.catch (fn [error]
                  (js/console.error (or (.-stack error) error))
                  (js/Deno.exit 1))))))

(set! *main-cli-fn* -main)
