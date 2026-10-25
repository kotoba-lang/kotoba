(ns torch.deno-public-gguf-continuous-verify
  "Real GGUF weights through ragged paged continuous Metal microbatches."
  (:require [num.array :as arr]
            [num.deno-gpu :as gpu]
            [torch.continuous :as continuous]
            [torch.deno-public-gguf-metal-verify :as metal]
            [torch.kv-cache :as kv]
            [torch.metal-bundle :as bundle]
            [torch.metal-paged :as metal-paged]
            [torch.num-backend :as nb]
            [torch.paged-runtime :as paged]))

(def storage metal-paged/storage)

(defn quiescent? [before after]
  (and (= (:live-buffers before) (:live-buffers after))
       (= (:live-bytes before) (:live-bytes after))
       (= (- (:created-buffers after) (:created-buffers before))
          (- (:destroyed-buffers after) (:destroyed-buffers before)))
       (= (- (:created-bytes after) (:created-bytes before))
          (- (:destroyed-bytes after) (:destroyed-bytes before)))))

(defn -main [& [bundle-path]]
  (let [bundle (bundle/load-bundle bundle-path)]
    (-> (gpu/request-device)
        (.then
         (fn [request]
           (let [backend (gpu/backend request)
                 baseline (gpu/backend-stats backend)
                 {:keys [embed-dim head-count kv-head-count block-count vocab]}
                 (:config bundle)
                 head-dim (quot embed-dim head-count)
                 block-size 2 pool-blocks 12
                 model* (metal/build-model (:config bundle))
                 weights (metal/upload-weights backend (:weights bundle))
                 storages (mapv (fn [_]
                                  (storage backend pool-blocks block-size
                                           head-count kv-head-count head-dim))
                                (range block-count))
                 runtimes (mapv #(paged/runtime (kv/pool pool-blocks block-size) %)
                                storages)
                 single-calls (atom []) batch-calls (atom [])
                 step-fn
                 (fn [token runtimes request-id]
                   (swap! single-calls conj [request-id token])
                   (let [token* (arr/from-vec backend [token] [1])
                         step (nb/llama-lm-paged-step
                               model* weights token* runtimes request-id)
                         logits (:logits step)]
                     (arr/release! token*)
                     (-> (arr/->vec logits)
                         (.then (fn [values]
                                  (arr/release! logits)
                                  (assoc step :logits (vec values)))))))
                 batch-step-fn
                 (fn [tokens runtimes request-ids]
                   (swap! batch-calls conj [request-ids tokens])
                   (let [tokens* (arr/from-vec backend tokens [(count tokens) 1])
                         step (nb/llama-lm-paged-batch-step
                               model* weights tokens* runtimes request-ids)
                         logits (:logits step)]
                     (arr/release! tokens*)
                     (-> (arr/->vec logits)
                         (.then (fn [values]
                                  (arr/release! logits)
                                  (assoc step :logits
                                         (mapv vec (partition vocab values))))))))
                 initial
                 (reduce (fn [engine* {:keys [id prompt-ids]}]
                           (continuous/enqueue
                            engine* id prompt-ids
                            {:temperature 0.0 :max-new-tokens 2 :eos-id -1}))
                         (continuous/engine runtimes step-fn batch-step-fn 2)
                         (:continuous-fixtures bundle))]
             (println "Public GGUF continuous decode on"
                      (gpu/adapter-description request))
             (letfn [(advance [engine* ticks]
                       (if (= 3 (count (:completed engine*)))
                         (js/Promise.resolve [engine* ticks])
                         (if (>= ticks 8)
                           (js/Promise.reject
                            (js/Error. "continuous decode did not finish"))
                           (-> (continuous/tick-batched-async engine*)
                               (.then #(advance % (inc ticks)))))))]
               (-> (continuous/admit-async initial)
                   (.then #(advance % 0))
                   (.then
                    (fn [[final ticks]]
                      (let [expected (into {}
                                           (map (juxt :id :generated-ids)
                                                (:continuous-fixtures bundle)))
                            actual (into {}
                                         (map (fn [[id result]]
                                                [id (:generated-ids result)]))
                                         (:completed final))
                            parity? (= expected actual)
                            ragged? (> (count (set (map #(count (:prompt-ids %))
                                                       (:continuous-fixtures bundle)))) 1)
                            batched? (some #(> (count (first %)) 1) @batch-calls)
                            pools-free? (every?
                                         #(and (= pool-blocks
                                                  (count (get-in % [:pool :free])))
                                               (kv/valid? (:pool %)))
                                         (:runtimes final))]
                        (println "CPU/continuous Metal token parity:"
                                 (if parity? "passed" "failed"))
                        (println "ragged real prompts in fused microbatch:"
                                 (if (and ragged? batched?) "passed" "failed"))
                        (println "ticks:" ticks "single calls:" (count @single-calls)
                                 "batch calls:" (count @batch-calls))
                        (println "paged blocks reusable:"
                                 (if pools-free? "passed" "failed"))
                        (doseq [{:keys [key-pool value-pool]} storages]
                          (arr/release-all! [key-pool value-pool]))
                        (nb/release-weights! weights)
                        (let [after (gpu/backend-stats backend)
                              released? (quiescent? baseline after)]
                          (println "GPU baseline restored:"
                                   (if released? "passed" "failed"))
                          (when-not (and parity? ragged? batched? pools-free?
                                         released?)
                            (throw (js/Error.
                                    "public GGUF continuous verification failed"))))))))))))
        (.then #(js/Deno.exit 0))
        (.catch (fn [error]
                  (println "ERROR:" (or (.-stack error) (str error)))
                  (js/Deno.exit 1))))))

(set! *main-cli-fn* -main)
