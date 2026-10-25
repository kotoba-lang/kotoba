(ns torch.deno-continuous-verify
  "Ragged continuous paged-Llama scheduling on Deno WebGPU -> Apple Metal."
  (:require [num.array :as arr]
            [num.deno-gpu :as gpu]
            [num.tensor :as t]
            [torch.continuous :as continuous]
            [torch.kv-cache :as kv]
            [torch.model :as model]
            [torch.num-backend :as nb]
            [torch.paged-runtime :as paged]))

(defn- metal-storage [backend]
  (let [key-pool (arr/zeros backend [3 2 2])
        value-pool (arr/zeros backend [3 2 2])]
    {:key-pool key-pool :value-pool value-pool
     :write! (fn [key value block offset]
               (gpu/paged-kv-write! key-pool value-pool key value block offset))
     :copy-block! (fn [source destination tokens]
                    (gpu/paged-kv-copy-block! key-pool value-pool
                                              source destination tokens))
     :attention
     (fn [query blocks length]
       (let [table (arr/from-vec backend blocks [(count blocks)])
             output (gpu/paged-gqa-attention query key-pool value-pool
                                             table length 2 1)]
         (arr/release! table)
         output))
     :attention-many
     (fn [query block-tables lengths]
       (let [batch (count lengths)
             max-blocks (apply max (map count block-tables))
             padded (vec (mapcat #(take max-blocks (concat % (repeat 0)))
                                 block-tables))
             tables* (arr/from-vec backend padded [batch max-blocks])
             lengths* (arr/from-vec backend lengths [batch])
             output (gpu/paged-gqa-attention-batch
                     (t/reshape query [batch (last (:shape query))])
                     key-pool value-pool tables* lengths* 2 1)]
         (arr/release-all! [tables* lengths*])
         (t/reshape output [batch 1 (last (:shape output))])))}))

(defn -main [& _]
  (-> (gpu/request-device)
      (.then
       (fn [device]
         (let [backend (gpu/backend device)
               model* (model/sequential
                       (model/embedding 6 4)
                       (model/llama-block 4 2 8 {:kv-heads 1})
                       (model/llama-block 4 2 8 {:kv-heads 1})
                       (model/rmsnorm 4) (model/lm-head 4 6))
               weights (nb/random-weights backend model* 89)
               storages (mapv (fn [_] (metal-storage backend)) (range 2))
               runtimes (mapv #(paged/runtime (kv/pool 3 2) %) storages)
               calls (atom [])
               batch-calls (atom [])
               step-fn
               (fn [token runtimes request-id]
                 (swap! calls conj [request-id token])
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
                                       (mapv vec (partition 6 values))))))))
               initial
               (-> (continuous/engine runtimes step-fn batch-step-fn 2)
                   (continuous/enqueue :a [2]
                                       {:temperature 0.0 :max-new-tokens 2
                                        :eos-id -1})
                   (continuous/enqueue :b [1 3 2]
                                       {:temperature 0.0 :max-new-tokens 2
                                        :eos-id -1})
                   (continuous/enqueue :c [4]
                                       {:temperature 0.0 :max-new-tokens 1
                                        :eos-id -1}))]
           (-> (continuous/admit-async initial)
               (.then continuous/tick-batched-async)
               (.then continuous/tick-batched-async)
               (.then continuous/tick-batched-async)
               (.then
                (fn [final]
                  (let [completed? (= #{:a :b :c}
                                      (set (keys (:completed final))))
                        pools-free? (every?
                                     #(and (= #{0 1 2}
                                              (set (get-in % [:pool :free])))
                                           (kv/valid? (:pool %)))
                                     (:runtimes final))
                        ragged? (and (= 5 (count @calls))
                                     (= 1 (count @batch-calls))
                                     (= [:a :b] (ffirst @batch-calls))
                                     (= [:a :b :c]
                                        (vec (keys (:completed final)))))
                        before-release (gpu/backend-stats backend)
                        _ (doseq [{:keys [key-pool value-pool]} storages]
                            (arr/release-all! [key-pool value-pool]))
                        after-release (gpu/backend-stats backend)
                        released? (and (= 4 (- (:live-buffers before-release)
                                                (:live-buffers after-release)))
                                       (= 192 (- (:live-bytes before-release)
                                                  (:live-bytes after-release))))]
                    (println "adapter:"
                             (or (gpu/adapter-description device) "unknown"))
                    (println "ragged continuous request turnover:"
                             (if (and completed? ragged?) "passed" "failed"))
                    (println "paged blocks fully reusable:"
                             (if pools-free? "passed" "failed"))
                    (println "shared physical pools release:"
                             (if released? "passed" "failed"))
                    (when-not (and completed? ragged? pools-free? released?)
                      (.exit js/Deno 1)))))))))
      (.catch (fn [error] (js/console.error error) (.exit js/Deno 1)))))

(set! *main-cli-fn* -main)
