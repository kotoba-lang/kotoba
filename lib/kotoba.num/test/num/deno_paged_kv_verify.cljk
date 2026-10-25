(ns num.deno-paged-kv-verify
  "Physical paged K/V storage and GQA decode on Deno WebGPU -> Apple Metal."
  (:require [num.array :as arr]
            [num.cpu :as cpu]
            [num.deno-gpu :as gpu]
            [num.tensor :as t]))

(defn- approx? [expected actual]
  (and (= (count expected) (count actual))
       (every? #(< (Math/abs %) 1.0e-5) (map - expected actual))))

(defn- cpu-attention [keys values query]
  (let [backend (cpu/cpu-backend)]
    (arr/->vec
     (t/multi-head-attention
      (arr/from-vec backend query [1 4])
      (arr/from-vec backend (vec (mapcat identity keys)) [(count keys) 2])
      (arr/from-vec backend (vec (mapcat identity values)) [(count values) 2])
      2 {:kv-heads 1}))))

(defn -main [& _]
  (let [keys [[1.0 0.0] [0.0 1.0] [0.5 -0.5]]
        values [[2.0 1.0] [4.0 -1.0] [3.0 5.0]]
        query [0.2 0.7 -0.4 0.6]
        child-key [-0.25 0.75]
        child-value [8.0 -2.0]
        expected (cpu-attention keys values query)
        expected-child (cpu-attention [(first keys) child-key]
                                      [(first values) child-value] query)]
    (-> (gpu/request-device)
        (.then
         (fn [device]
           (let [backend (gpu/backend device)
                 baseline (gpu/backend-stats backend)
                 key-pool (arr/zeros backend [4 2 2])
                 value-pool (arr/zeros backend [4 2 2])
                 query* (arr/from-vec backend query [1 4])
                 token-arrays
                 (mapv (fn [[key value]]
                         [(arr/from-vec backend key [1 2])
                          (arr/from-vec backend value [1 2])])
                       (map vector keys values))
                 _ (gpu/paged-kv-write! key-pool value-pool
                                        (get-in token-arrays [0 0])
                                        (get-in token-arrays [0 1]) 2 0)
                 _ (gpu/paged-kv-write! key-pool value-pool
                                        (get-in token-arrays [1 0])
                                        (get-in token-arrays [1 1]) 2 1)
                 _ (gpu/paged-kv-write! key-pool value-pool
                                        (get-in token-arrays [2 0])
                                        (get-in token-arrays [2 1]) 0 0)
                 table (arr/from-vec backend [2 0] [2])
                 output (gpu/paged-gqa-attention query* key-pool value-pool
                                                 table 3 2 1)
                 ;; Fork after one token: copy the used prefix of block 2 to
                 ;; block 1, then write a divergent second token.
                 _ (gpu/paged-kv-copy-block! key-pool value-pool 2 1 1)
                 child-k (arr/from-vec backend child-key [1 2])
                 child-v (arr/from-vec backend child-value [1 2])
                 _ (gpu/paged-kv-write! key-pool value-pool child-k child-v 1 1)
                 child-table (arr/from-vec backend [1] [1])
                 child-output (gpu/paged-gqa-attention
                               query* key-pool value-pool child-table 2 2 1)
                 batch-query (arr/from-vec backend (vec (concat query query)) [2 4])
                 batch-tables (arr/from-vec backend [2 0 1 0] [2 2])
                 batch-lengths (arr/from-vec backend [3 2] [2])
                 batch-output
                 (gpu/paged-gqa-attention-batch
                  batch-query key-pool value-pool batch-tables batch-lengths 2 1)]
             (-> (js/Promise.all
                  #js [(arr/->vec output) (arr/->vec child-output)
                       (arr/->vec batch-output)])
                 (.then
                  (fn [reads]
                    (let [actual (vec (aget reads 0))
                          actual-child (vec (aget reads 1))
                          actual-batch (vec (aget reads 2))
                          parity? (approx? expected actual)
                          cow? (approx? expected-child actual-child)
                          batch? (approx? (vec (concat expected expected-child))
                                          actual-batch)
                          arrays (concat [key-pool value-pool query* table output
                                          child-k child-v child-table child-output
                                          batch-query batch-tables batch-lengths
                                          batch-output]
                                         (mapcat identity token-arrays))]
                      (arr/release-all! arrays)
                      (let [after (gpu/backend-stats backend)
                            released? (and (= (:live-buffers baseline)
                                              (:live-buffers after))
                                           (= (:live-bytes baseline)
                                              (:live-bytes after)))]
                        (println "adapter:"
                                 (or (gpu/adapter-description device) "unknown"))
                        (println "non-contiguous paged GQA parity:"
                                 (if parity? "passed" "failed"))
                        (println "prefix COW block-copy parity:"
                                 (if cow? "passed" "failed"))
                        (println "ragged batched paged GQA parity:"
                                 (if batch? "passed" "failed"))
                        (println "paged GPU storage release:"
                                 (if released? "passed" "failed"))
                        (when-not (and parity? cow? batch? released?)
                          (.exit js/Deno 1))))))))))
        (.catch (fn [error] (js/console.error error) (.exit js/Deno 1))))))

(set! *main-cli-fn* -main)
