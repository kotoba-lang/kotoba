(ns torch.deno-kv-cache-verify
  "Device-resident incremental KV-cache parity on Deno WebGPU -> Apple Metal."
  (:require [num.array :as arr]
            [num.cpu :as cpu]
            [num.deno-gpu :as gpu]
            [torch.core :as core]
            [torch.model :as model]
            [torch.num-backend :as nb]))

(def tokens
  [[0.2 -0.1 0.3 0.4]
   [-0.2 0.1 0.5 -0.3]
   [0.6 0.2 -0.4 0.1]
   [-0.1 0.4 0.2 -0.5]])

(def token-ids [2 0 2 1])
(def batched-token-ids [[2 0 2] [1 3 4]])

(def batched-tokens
  [[[0.2 -0.1 0.3 0.4]
    [-0.2 0.1 0.5 -0.3]
    [0.6 0.2 -0.4 0.1]]
   [[-0.3 0.7 0.1 -0.2]
    [0.4 -0.5 0.2 0.6]
    [0.1 0.3 -0.7 0.2]]])

(defn- approx? [expected actual]
  (and (= (count expected) (count actual))
       (every? #(< (Math/abs %) 1.0e-5) (map - expected actual))))

(defn- decode [backend layer weights initial-cache]
  (reduce (fn [{:keys [cache outputs stale]} token]
            (let [step (nb/multihead-attention-step
                        layer weights (arr/from-vec backend token [1 4]) cache)]
              {:cache (:cache step)
               :outputs (conj outputs (:output step))
               :stale (cond-> stale cache (conj cache))}))
          {:cache initial-cache :outputs [] :stale []} tokens))

(defn- decode-llama [backend model* weights caches]
  (reduce (fn [{:keys [caches outputs]} token]
            (let [step (nb/llama-lm-step
                        model* weights (arr/from-vec backend [token] [1]) caches)]
              {:caches (:caches step) :outputs (conj outputs (:logits step))}))
          {:caches caches :outputs []} token-ids))

(defn- decode-batched [backend layer weights initial-cache]
  (reduce (fn [{:keys [cache outputs]} time]
            (let [values (vec (mapcat #(nth % time) batched-tokens))
                  step (nb/multihead-attention-step
                        layer weights (arr/from-vec backend values [2 1 4]) cache)]
              {:cache (:cache step) :outputs (conj outputs (:output step))}))
          {:cache initial-cache :outputs []} (range 3)))

(defn- decode-batched-llama [backend model* weights caches]
  (reduce (fn [{:keys [caches outputs]} time]
            (let [ids (mapv #(nth % time) batched-token-ids)
                  step (nb/llama-lm-step
                        model* weights (arr/from-vec backend ids [2 1]) caches)]
              {:caches (:caches step) :outputs (conj outputs (:logits step))}))
          {:caches caches :outputs []} (range 3)))

(defn -main [& _]
  (let [layer (model/multihead-attention
               4 2 {:causal? true :rope? true :position-offset 3})
        model* (model/sequential layer)
        llama-model (model/sequential
                     (model/embedding 6 4)
                     (model/llama-block 4 2 8 {:position-offset 3 :kv-heads 1})
                     (model/llama-block 4 2 8 {:position-offset 3 :kv-heads 1})
                     (model/rmsnorm 4) (model/lm-head 4 6))
        cpu-backend (cpu/cpu-backend)
        cpu-weights (nb/random-weights cpu-backend model* 61)
        input-values (vec (mapcat identity tokens))
        expected (arr/->vec
                  (core/run (nb/num-backend cpu-backend cpu-weights) model*
                            (arr/from-vec cpu-backend input-values [4 4])))
        batched-input-values (vec (mapcat identity (mapcat identity batched-tokens)))
        expected-batched
        (arr/->vec
         (core/run (nb/num-backend cpu-backend cpu-weights) model*
                   (arr/from-vec cpu-backend batched-input-values [2 3 4])))
        cpu-llama-weights (nb/random-weights cpu-backend llama-model 71)
        expected-llama
        (arr/->vec (core/run (nb/num-backend cpu-backend cpu-llama-weights)
                             llama-model
                             (arr/from-vec cpu-backend token-ids [4])))
        expected-batched-llama
        (arr/->vec
         (core/run (nb/num-backend cpu-backend cpu-llama-weights)
                   llama-model
                   (arr/from-vec cpu-backend (vec (mapcat identity batched-token-ids))
                                 [2 3])))]
    (-> (gpu/request-device)
        (.then
         (fn [device]
           (let [backend (gpu/backend device)
                 weights (nb/random-weights backend model* 61)
                 full (core/run (nb/num-backend backend weights) model*
                                (arr/from-vec backend input-values [4 4]))
                 initial-cache (nb/init-kv-cache backend 16 4)
                 key-handle (:handle (:key initial-cache))
                 value-handle (:handle (:value initial-cache))
                 decoded (decode backend layer (first weights) initial-cache)
                 batched-full
                 (core/run (nb/num-backend backend weights) model*
                           (arr/from-vec backend batched-input-values [2 3 4]))
                 batched-initial (nb/init-kv-cache backend 16 4 :f32 2)
                 batched-key-handle (:handle (:key batched-initial))
                 batched-decoded (decode-batched backend layer (first weights)
                                                   batched-initial)
                 llama-weights (nb/random-weights backend llama-model 71)
                 llama-full (core/run (nb/num-backend backend llama-weights)
                                      llama-model
                                      (arr/from-vec backend token-ids [4]))
                 llama-initial (nb/init-llama-caches backend llama-model 16)
                 llama-handles (mapv #(-> % :key :handle) llama-initial)
                 llama-decoded (decode-llama backend llama-model llama-weights
                                             llama-initial)
                 batched-llama-full
                 (core/run (nb/num-backend backend llama-weights) llama-model
                           (arr/from-vec backend
                                         (vec (mapcat identity batched-token-ids))
                                         [2 3]))
                 batched-llama-initial
                 (nb/init-llama-caches backend llama-model 16 :f32 2)
                 batched-llama-handles
                 (mapv #(-> % :key :handle) batched-llama-initial)
                 batched-llama-decoded
                 (decode-batched-llama backend llama-model llama-weights
                                       batched-llama-initial)
                 reads (into [(arr/->vec full)] (map arr/->vec (:outputs decoded)))
                 reads (into reads [(arr/->vec llama-full)])
                 reads (into reads (map arr/->vec (:outputs llama-decoded)))
                 reads (into reads [(arr/->vec batched-full)])
                 reads (into reads (map arr/->vec (:outputs batched-decoded)))
                 reads (into reads [(arr/->vec batched-llama-full)])
                 reads (into reads (map arr/->vec (:outputs batched-llama-decoded)))]
             (.then (js/Promise.all (into-array reads))
                    (fn [values]
                      (let [full-values (vec (aget values 0))
                            step-values (vec (mapcat #(vec (aget values %)) (range 1 5)))
                            llama-full-values (vec (aget values 5))
                            llama-step-values (vec (mapcat #(vec (aget values %))
                                                           (range 6 10)))
                            batched-full-values (vec (aget values 10))
                            batched-steps (mapv #(vec (aget values %)) (range 11 14))
                            batched-step-values
                            (vec (for [batch (range 2) time (range 3)
                                       feature (range 4)]
                                   (nth (nth batched-steps time)
                                        (+ (* batch 4) feature))))
                            batched-llama-full-values (vec (aget values 14))
                            batched-llama-steps
                            (mapv #(vec (aget values %)) (range 15 18))
                            batched-llama-step-values
                            (vec (for [batch (range 2) time (range 3)
                                       vocab (range 6)]
                                   (nth (nth batched-llama-steps time)
                                        (+ (* batch 6) vocab))))
                            full-ok? (approx? expected full-values)
                            cache-ok? (approx? expected step-values)
                            llama-ok? (and (approx? expected-llama llama-full-values)
                                           (approx? expected-llama llama-step-values)
                                           (every? true?
                                                   (map identical? llama-handles
                                                        (map #(-> % :key :handle)
                                                             (:caches llama-decoded)))))
                            batched-ok?
                            (and (approx? expected-batched batched-full-values)
                                 (approx? expected-batched batched-step-values)
                                 (= 2 (get-in batched-decoded [:cache :batch]))
                                 (= 3 (get-in batched-decoded [:cache :length]))
                                 (identical? batched-key-handle
                                             (:handle
                                              (get-in batched-decoded [:cache :key]))))
                            batched-llama-ok?
                            (and (approx? expected-batched-llama
                                          batched-llama-full-values)
                                 (approx? expected-batched-llama
                                          batched-llama-step-values)
                                 (= [3 3]
                                    (mapv :length (:caches batched-llama-decoded)))
                                 (every? true?
                                         (map identical? batched-llama-handles
                                              (map #(-> % :key :handle)
                                                   (:caches batched-llama-decoded)))))
                            device-cache? (and (= 4 (get-in decoded [:cache :length]))
                                               (= 16 (get-in decoded [:cache :capacity]))
                                               (identical? key-handle
                                                           (:handle
                                                            (get-in decoded [:cache :key])))
                                               (identical? value-handle
                                                           (:handle
                                                            (get-in decoded [:cache :value])))
                                               (some? (.-size
                                                       (:handle
                                                        (get-in decoded [:cache :key])))))
                            before-release (gpu/backend-stats backend)
                            _ (do
                                (nb/release-kv-cache! (:cache decoded))
                                (nb/release-kv-cache! (:cache batched-decoded))
                                (nb/release-llama-caches! (:caches llama-decoded))
                                (nb/release-llama-caches!
                                 (:caches batched-llama-decoded)))
                            after-release (gpu/backend-stats backend)
                            released?
                            (and (= 12 (- (:live-buffers before-release)
                                          (:live-buffers after-release)))
                                 (= 3072 (- (:live-bytes before-release)
                                            (:live-bytes after-release))))]
                        (println "adapter:" (or (gpu/adapter-description device) "unknown"))
                        (println "full causal Metal parity:" (if full-ok? "passed" "failed"))
                        (println "device-resident KV-cache parity:"
                                 (if (and cache-ok? device-cache?) "passed" "failed"))
                        (println "two-block Llama cached decode parity:"
                                 (if llama-ok? "passed" "failed"))
                        (println "batched fixed KV-cache Metal parity:"
                                 (if batched-ok? "passed" "failed"))
                        (println "batched two-block Llama Metal parity:"
                                 (if batched-llama-ok? "passed" "failed"))
                        (println "fixed cache release (12 buffers / 3072 bytes):"
                                 (if released? "passed" "failed"))
                        (when-not (and full-ok? cache-ok? device-cache? llama-ok?
                                       batched-ok? batched-llama-ok? released?)
                          (.exit js/Deno 1))))))))
        (.catch (fn [error] (js/console.error error) (.exit js/Deno 1))))))

(set! *main-cli-fn* -main)
