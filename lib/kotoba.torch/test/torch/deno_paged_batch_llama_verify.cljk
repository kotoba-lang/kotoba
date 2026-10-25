(ns torch.deno-paged-batch-llama-verify
  "Fused multi-request paged Llama attention on Apple Metal."
  (:require [num.array :as arr]
            [num.cpu :as cpu]
            [num.deno-gpu :as gpu]
            [num.tensor :as t]
            [torch.core :as core]
            [torch.kv-cache :as kv]
            [torch.model :as model]
            [torch.num-backend :as nb]
            [torch.paged-runtime :as paged]))

(defn- approx? [expected actual]
  (and (= (count expected) (count actual))
       (every? #(< (Math/abs %) 1.0e-5) (map - expected actual))))

(defn- metal-storage [backend]
  (let [key-pool (arr/zeros backend [5 2 2])
        value-pool (arr/zeros backend [5 2 2])]
    {:key-pool key-pool :value-pool value-pool
     :write! (fn [key value block offset]
               (gpu/paged-kv-write! key-pool value-pool key value block offset))
     :copy-block! (fn [source destination tokens]
                    (gpu/paged-kv-copy-block! key-pool value-pool
                                              source destination tokens))
     :attention (fn [query blocks length]
                  (let [table (arr/from-vec backend blocks [(count blocks)])
                        output (gpu/paged-gqa-attention
                                query key-pool value-pool table length 2 1)]
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
             flat-query (t/reshape query [batch (last (:shape query))])
             output (gpu/paged-gqa-attention-batch
                     flat-query key-pool value-pool tables* lengths* 2 1)]
         (arr/release-all! [tables* lengths*])
         (t/reshape output [batch 1 (last (:shape output))])))}))

(defn -main [& _]
  (let [model* (model/sequential
                (model/embedding 6 4)
                (model/llama-block 4 2 8 {:kv-heads 1})
                (model/llama-block 4 2 8 {:kv-heads 1})
                (model/rmsnorm 4) (model/lm-head 4 6))
        cpu-backend (cpu/cpu-backend)
        cpu-weights (nb/random-weights cpu-backend model* 91)
        full-a (arr/->vec
                (core/run (nb/num-backend cpu-backend cpu-weights) model*
                          (arr/from-vec cpu-backend [2 0] [2])))
        full-b (arr/->vec
                (core/run (nb/num-backend cpu-backend cpu-weights) model*
                          (arr/from-vec cpu-backend [1 3 2] [3])))
        expected (vec (concat (subvec full-a 6 12) (subvec full-b 12 18)))]
    (-> (gpu/request-device)
        (.then
         (fn [device]
           (let [backend (gpu/backend device)
                 weights (nb/random-weights backend model* 91)
                 storages (mapv (fn [_] (metal-storage backend)) (range 2))
                 runtimes (mapv (fn [storage]
                                  (-> (paged/runtime (kv/pool 5 2) storage)
                                      (paged/allocate-sequence :a)
                                      (paged/allocate-sequence :b)))
                                storages)
                 a (nb/llama-lm-paged-step
                    model* weights (arr/from-vec backend [2] [1]) runtimes :a)
                 b1 (nb/llama-lm-paged-step
                     model* weights (arr/from-vec backend [1] [1])
                     (:runtimes a) :b)
                 b2 (nb/llama-lm-paged-step
                     model* weights (arr/from-vec backend [3] [1])
                     (:runtimes b1) :b)
                 batch (nb/llama-lm-paged-batch-step
                        model* weights (arr/from-vec backend [0 2] [2 1])
                        (:runtimes b2) [:a :b])]
             (-> (arr/->vec (:logits batch))
                 (.then
                  (fn [values]
                    (let [parity? (approx? expected (vec values))
                          lengths? (= [[2 3] [2 3]]
                                      (mapv (fn [runtime*]
                                              [(get-in runtime*
                                                       [:pool :sequences :a :length])
                                               (get-in runtime*
                                                       [:pool :sequences :b :length])])
                                            (:runtimes batch)))
                          before (gpu/backend-stats backend)
                          _ (doseq [{:keys [key-pool value-pool]} storages]
                              (arr/release-all! [key-pool value-pool]))
                          after (gpu/backend-stats backend)
                          released? (and (= 4 (- (:live-buffers before)
                                                  (:live-buffers after)))
                                         (= 320 (- (:live-bytes before)
                                                   (:live-bytes after))))]
                      (println "adapter:"
                               (or (gpu/adapter-description device) "unknown"))
                      (println "ragged fused paged Llama parity:"
                               (if (and parity? lengths?) "passed" "failed"))
                      (println "batched physical pools release:"
                               (if released? "passed" "failed"))
                      (when-not (and parity? lengths? released?)
                        (.exit js/Deno 1)))))))))
        (.catch (fn [error] (js/console.error error) (.exit js/Deno 1))))))

(set! *main-cli-fn* -main)
