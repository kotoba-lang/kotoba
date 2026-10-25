(ns torch.deno-autocast-verify
  "Live torch model autocast verification on Deno→Apple Metal."
  (:require [num.array :as arr]
            [num.cpu :as cpu]
            [num.deno-gpu :as gpu]
            [torch.core :as core]
            [torch.model :as model]
            [torch.num-backend :as backend]
            [torch.optim :as optim]
            [torch.train :as train]))

(defn- approx-vec? [expected actual tolerance]
  (and (= (count expected) (count actual))
       (every? true? (map #(< (Math/abs (- %1 %2)) tolerance)
                          expected actual))))

(defn -main [& _]
  (let [model* (model/sequential (model/conv2d 2 4 3 1 1)
                                 (model/groupnorm 2 4) (model/layernorm 4)
                                 (model/silu) (model/sigmoid) (model/tanh) (model/gelu))
        embedding-model (model/sequential (model/embedding 5 4)
                                          (model/rmsnorm 4) (model/gelu))
        attention-model (model/sequential (model/multihead-attention 4 1))
        attention-input-values [0.1 0.2 0.3 0.4, -0.2 0.1 0.5 -0.3]
        attention-target-values [0.2 0.0 0.1 -0.1, -0.1 0.3 0.2 0.0]
        input-values (mapv #(- (* 0.03 %) 0.4) (range 32))
        token-values [2 0 2 1]
        cpu-backend (cpu/cpu-backend)
        cpu-weights (backend/random-weights cpu-backend model* 3 {:dtype :f16})
        cpu-embedding-weights (backend/random-weights cpu-backend embedding-model 7
                                                      {:dtype :f16})
        expected (arr/->vec
                  (core/run (backend/num-backend cpu-backend cpu-weights
                                                 {:autocast-dtype :f16})
                            model*
                            (arr/from-vec cpu-backend input-values [1 2 4 4] :f16)))
        expected-embedding
        (arr/->vec
         (core/run (backend/num-backend cpu-backend cpu-embedding-weights
                                        {:autocast-dtype :f16})
                   embedding-model (arr/from-vec cpu-backend token-values [4])))
        expected-attention
        (arr/->vec
         (core/run (backend/num-backend
                    cpu-backend (backend/random-weights cpu-backend attention-model 11))
                   attention-model
                   (arr/from-vec cpu-backend attention-input-values [1 2 4])))
        cpu-training
        (train/loss-and-gradients
         attention-model (backend/random-weights cpu-backend attention-model 11)
         (arr/from-vec cpu-backend attention-input-values [1 2 4])
         (arr/from-vec cpu-backend attention-target-values [1 2 4])
         {:autocast-dtype :f16 :loss-scale 8.0})
        expected-training-gradients
        (mapv (fn [key] (arr/->vec (get (first (:gradients cpu-training)) key)))
              [:qw :qb :kw :kb :vw :vb :ow :ob])
        scaler (optim/grad-scaler {:initial-scale 8.0 :growth-interval 2})
        adamw-options {:learning-rate 0.01 :weight-decay 0.001}
        cpu-mixed
        (train/mixed-precision-adamw-step
         attention-model (backend/random-weights cpu-backend attention-model 11)
         (arr/from-vec cpu-backend attention-input-values [1 2 4])
         (arr/from-vec cpu-backend attention-target-values [1 2 4])
         nil scaler {:autocast-dtype :f16 :adamw-options adamw-options})
        expected-updated
        (mapv (fn [key] (arr/->vec (get (first (:weights cpu-mixed)) key)))
              [:qw :qb :kw :kb :vw :vb :ow :ob])]
    (-> (gpu/request-device)
        (.then
         (fn [device-result]
           (let [gpu-backend (gpu/backend device-result)
                 weights (backend/random-weights gpu-backend model* 3 {:dtype :f16})
                 input (arr/from-vec gpu-backend input-values [1 2 4 4] :f16)
                 output (core/run (backend/num-backend gpu-backend weights
                                                       {:autocast-dtype :f16})
                                  model* input)
                 embedding-weights (backend/random-weights gpu-backend embedding-model 7
                                                            {:dtype :f16})
                 embedding-output
                 (core/run (backend/num-backend gpu-backend embedding-weights
                                                {:autocast-dtype :f16})
                           embedding-model
                           (arr/from-vec gpu-backend token-values [4]))
                 attention-weights (backend/random-weights gpu-backend attention-model 11
                                                           {:dtype :f16})
                 attention-output
                 (core/run (backend/num-backend gpu-backend attention-weights
                                                {:autocast-dtype :f16})
                           attention-model
                           (arr/from-vec gpu-backend attention-input-values [1 2 4]
                                         :f16))
                 gpu-training
                 (train/loss-and-gradients
                  attention-model
                  (backend/random-weights gpu-backend attention-model 11)
                  (arr/from-vec gpu-backend attention-input-values [1 2 4])
                  (arr/from-vec gpu-backend attention-target-values [1 2 4])
                  {:autocast-dtype :f16 :loss-scale 8.0})
                 gpu-training-gradients
                 (mapv #(get (first (:gradients gpu-training)) %)
                       [:qw :qb :kw :kb :vw :vb :ow :ob])
                 gpu-mixed
                 (train/mixed-precision-adamw-step-async
                  attention-model
                  (backend/random-weights gpu-backend attention-model 11)
                  (arr/from-vec gpu-backend attention-input-values [1 2 4])
                  (arr/from-vec gpu-backend attention-target-values [1 2 4])
                  nil scaler {:autocast-dtype :f16 :adamw-options adamw-options})
                 gpu-mixed-values
                 (.then gpu-mixed
                        (fn [result]
                          (.then
                           (js/Promise.all
                            (into-array
                             (map #(arr/->vec (get (first (:weights result)) %))
                                  [:qw :qb :kw :kb :vw :vb :ow :ob])))
                           (fn [values] [result (mapv vec (array-seq values))]))))]
             (println "adapter:" (or (gpu/adapter-description device-result) "unknown"))
             (.then (js/Promise.all (into-array [(arr/->vec output)
                                                 (arr/->vec embedding-output)
                                                 (arr/->vec attention-output)
                                                 (:loss gpu-training)
                                                 (arr/->vec (:prediction gpu-training))
                                                 (js/Promise.all
                                                  (into-array
                                                   (map arr/->vec
                                                        gpu-training-gradients)))
                                                 gpu-mixed-values]))
                    (fn [actual-values]
                      (let [actual (vec (aget actual-values 0))
                            actual-embedding (vec (aget actual-values 1))
                            actual-attention (vec (aget actual-values 2))
                            actual-loss (aget actual-values 3)
                            actual-training-prediction (vec (aget actual-values 4))
                            actual-gradients (mapv vec (array-seq (aget actual-values 5)))
                            [actual-mixed actual-updated] (aget actual-values 6)
                            ok? (approx-vec? expected actual 0.03)
                            embedding-ok? (approx-vec? expected-embedding
                                                        actual-embedding 0.01)
                            attention-ok? (approx-vec? expected-attention
                                                        actual-attention 0.03)
                            training-ok?
                            (and (< (Math/abs (- actual-loss (:loss cpu-training))) 0.01)
                                 (approx-vec? (arr/->vec (:prediction cpu-training))
                                              actual-training-prediction 0.03)
                                 (every? true?
                                         (map #(approx-vec? %1 %2 0.04)
                                              expected-training-gradients
                                              actual-gradients))
                                 (= :f16 (:dtype (:prediction gpu-training)))
                                 (every? #(= :f32 (:dtype %)) gpu-training-gradients))
                            mixed-step-ok?
                            (and (false? (:skipped? actual-mixed))
                                 (= 1 (get-in actual-mixed [:optimizer-state :step]))
                                 (= (:scale scaler) (get-in actual-mixed [:scaler :scale]))
                                 (every? true?
                                         (map #(approx-vec? %1 %2 0.04)
                                              expected-updated actual-updated)))]
                        (println (str "torch conv→GroupNorm→LayerNorm→activations f16: "
                                      (if ok? "passed" "failed")))
                        (println (str "torch Embedding→RMSNorm→GELU f16: "
                                      (if embedding-ok? "passed" "failed")))
                        (println (str "torch learned attention f16: "
                                      (if attention-ok? "passed" "failed")))
                        (println (str "torch learned attention f16 backward: "
                                      (if training-ok? "passed" "failed")))
                        (println (str "torch learned attention async AdamW: "
                                      (if mixed-step-ok? "passed" "failed")))
                        (when-not (and ok? embedding-ok? attention-ok? training-ok?
                                       mixed-step-ok?)
                          (.exit js/Deno 1))))))))
        (.catch (fn [error]
                  (js/console.error error)
                  (.exit js/Deno 1))))))

(set! *main-cli-fn* -main)
