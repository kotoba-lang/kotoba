(ns torch.deno-paged-llama-verify
  "End-to-end paged Llama decode through num.deno-gpu on Apple Metal."
  (:require [num.array :as arr]
            [num.cpu :as cpu]
            [num.deno-gpu :as gpu]
            [torch.core :as core]
            [torch.kv-cache :as kv]
            [torch.model :as model]
            [torch.num-backend :as nb]
            [torch.paged-runtime :as paged]))

(defn- approx? [expected actual]
  (and (= (count expected) (count actual))
       (every? #(< (Math/abs %) 1.0e-5) (map - expected actual))))

(defn- metal-storage [backend block-count block-size heads kv-heads head-dim]
  (let [kv-width (* kv-heads head-dim)
        key-pool (arr/zeros backend [block-count block-size kv-width])
        value-pool (arr/zeros backend [block-count block-size kv-width])]
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
                                             table length heads kv-heads)]
         ;; Queue submission captured the table buffer; it may be retired now.
         (arr/release! table)
         output))}))

(defn -main [& _]
  (let [model* (model/sequential
                (model/embedding 6 4)
                (model/llama-block 4 2 8 {:kv-heads 1})
                (model/llama-block 4 2 8 {:kv-heads 1})
                (model/rmsnorm 4) (model/lm-head 4 6))
        token-ids [2 0 2 1]
        cpu-backend (cpu/cpu-backend)
        cpu-weights (nb/random-weights cpu-backend model* 83)
        expected
        (arr/->vec
         (core/run (nb/num-backend cpu-backend cpu-weights) model*
                   (arr/from-vec cpu-backend token-ids [4])))]
    (-> (gpu/request-device)
        (.then
         (fn [device]
           (let [backend (gpu/backend device)
                 weights (nb/random-weights backend model* 83)
                 storages (mapv (fn [_] (metal-storage backend 4 2 2 1 2))
                                (range 2))
                 runtimes (mapv (fn [storage]
                                  (-> (paged/runtime (kv/pool 4 2) storage)
                                      (paged/allocate-sequence :request)))
                                storages)
                 decoded
                 (reduce (fn [{:keys [runtimes outputs placements]} token]
                           (let [token* (arr/from-vec backend [token] [1])
                                 step (nb/llama-lm-paged-step
                                       model* weights token* runtimes :request)]
                             (arr/release! token*)
                             {:runtimes (:runtimes step)
                              :outputs (conj outputs (:logits step))
                              :placements (conj placements (:placements step))}))
                         {:runtimes runtimes :outputs [] :placements []}
                         token-ids)
                 reads (mapv arr/->vec (:outputs decoded))]
             (-> (js/Promise.all (clj->js reads))
                 (.then
                  (fn [values]
                    (let [actual (vec (mapcat #(vec (aget values %))
                                              (range (count token-ids))))
                          parity? (approx? expected actual)
                          tables-ok?
                          (and (= [[{:block 0 :offset 0} {:block 0 :offset 0}]
                                   [{:block 0 :offset 1} {:block 0 :offset 1}]
                                   [{:block 1 :offset 0} {:block 1 :offset 0}]
                                   [{:block 1 :offset 1} {:block 1 :offset 1}]]
                                  (:placements decoded))
                               (every? #(kv/valid? (:pool %))
                                       (:runtimes decoded)))
                          before-release (gpu/backend-stats backend)
                          _ (doseq [{:keys [key-pool value-pool]} storages]
                              (arr/release-all! [key-pool value-pool]))
                          after-release (gpu/backend-stats backend)
                          pools-released?
                          (and (= 4 (- (:live-buffers before-release)
                                       (:live-buffers after-release)))
                               (= 256 (- (:live-bytes before-release)
                                         (:live-bytes after-release))))]
                      (println "adapter:"
                               (or (gpu/adapter-description device) "unknown"))
                      (println "full two-block paged Llama parity:"
                               (if parity? "passed" "failed"))
                      (println "allocator/device placement alignment:"
                               (if tables-ok? "passed" "failed"))
                      (println "physical paged pools release:"
                               (if pools-released? "passed" "failed"))
                      (when-not (and parity? tables-ok? pools-released?)
                        (.exit js/Deno 1)))))))))
        (.catch (fn [error] (js/console.error error) (.exit js/Deno 1))))))

(set! *main-cli-fn* -main)
