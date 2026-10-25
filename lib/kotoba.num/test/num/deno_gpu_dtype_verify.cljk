(ns num.deno-gpu-dtype-verify
  "Live shader-f16 verification against the CPU typed-storage oracle."
  (:require [num.array :as arr]
            [num.autograd :as ag :include-macros true]
            [num.core :as num]
            [num.cpu :as cpu]
            [num.deno-gpu :as gpu]
            [num.tensor :as tensor]))

(defn- approx-vec? [expected actual tolerance]
  (and (= (count expected) (count actual))
       (every? true? (map #(< (Math/abs (- %1 %2)) tolerance)
                          expected actual))))

(defn -main [& _]
  (let [cpu-backend (cpu/cpu-backend)
        cpu-a (arr/from-vec cpu-backend [1.0 2.0 3.0 4.0] [2 2] :f16)
        cpu-b (arr/from-vec cpu-backend [0.5 -1.0 2.0 0.25] [2 2] :f16)
        conv-input-values (mapv #(- (* 0.03 %) 0.4) (range 32))
        conv-weight-values (mapv #(- (* 0.02 (mod % 17)) 0.12) (range 72))
        conv-bias-values [0.01 -0.02 0.03 -0.04]
        cpu-conv (tensor/conv2d-nchw
                  (arr/from-vec cpu-backend conv-input-values [1 2 4 4] :f16)
                  (arr/from-vec cpu-backend conv-weight-values [4 2 3 3] :f16)
                  (arr/from-vec cpu-backend conv-bias-values [4] :f16)
                  {:padding 1})
        cpu-norm (tensor/group-norm-nchw
                  cpu-conv 2
                  (arr/from-vec cpu-backend [0.9 1.0 1.1 1.2] [4] :f16)
                  (arr/from-vec cpu-backend [0.01 -0.02 0.03 -0.04] [4] :f16)
                  1.0e-5)
        cpu-norm-silu (tensor/group-norm-silu-nchw
                       cpu-conv 2
                       (arr/from-vec cpu-backend [0.9 1.0 1.1 1.2] [4] :f16)
                       (arr/from-vec cpu-backend [0.01 -0.02 0.03 -0.04] [4] :f16)
                       1.0e-5)
        cpu-layernorm (tensor/layer-norm-last
                       cpu-a
                       (arr/from-vec cpu-backend [0.9 1.1] [2] :f16)
                       (arr/from-vec cpu-backend [0.1 -0.2] [2] :f16) 1.0e-5)
        embedding-indices [2 0 2 1]
        embedding-weights [0.1 0.2, -0.2 0.4, 0.7 -0.1]
        cpu-embedding (tensor/embedding
                       (arr/from-vec cpu-backend embedding-indices [4])
                       (arr/from-vec cpu-backend embedding-weights [3 2] :f16))
        rms-weight-values [0.9 1.1]
        cpu-rmsnorm (tensor/rms-norm-last
                     cpu-a (arr/from-vec cpu-backend rms-weight-values [2] :f16))
        rope-opts {:position-offset 2}
        cpu-rope (tensor/rotary-embedding cpu-a 1 rope-opts)
        cpu-copy-destination (arr/zeros cpu-backend [6] :f16)
        _ (tensor/copy-into! cpu-copy-destination
                             (arr/from-vec cpu-backend [0.25 -0.5] [2] :f16) 2)
        cpu-odd (arr/from-vec cpu-backend [1 2 3 4 5] [1 1 1 5] :f16)
        cpu-slice (tensor/slice-axis cpu-odd 3 1 4)
        cpu-upsample (tensor/upsample-nearest2d
                      (arr/from-vec cpu-backend [1 2 3] [1 1 1 3] :f16) [2 2])
        cpu-scaled (tensor/scale cpu-odd 0.25)
        attention-values [0.1 0.2 0.3 0.4, -0.2 0.1 0.5 -0.3]
        cpu-attention (tensor/multi-head-attention
                       (arr/from-vec cpu-backend attention-values [1 2 4])
                       (arr/from-vec cpu-backend attention-values [1 2 4])
                       (arr/from-vec cpu-backend [1 2 3 4, 5 6 7 8] [1 2 4]) 1)
        attention-upstream [0.2 -0.1 0.3 -0.2, 0.1 0.4 -0.3 0.2]
        [cpu-gradient-result cpu-gradient-tape]
        (ag/with-tape
          (let [q (ag/value (arr/from-vec cpu-backend attention-values [1 2 4]))
                k (ag/value (arr/from-vec cpu-backend attention-values [1 2 4]))
                v (ag/value (arr/from-vec cpu-backend [1 2 3 4, 5 6 7 8]
                                                [1 2 4]))
                output (ag/multi-head-attention* q k v 1)]
            {:q q :k k :v v :output output}))
        _ (ag/backward! (:output cpu-gradient-result)
                        (arr/from-vec cpu-backend attention-upstream [1 2 4])
                        cpu-gradient-tape)
        expected [(arr/->vec (num/add cpu-a cpu-b))
                  (arr/->vec (num/silu cpu-a))
                  (arr/->vec (num/sigmoid cpu-a))
                  (arr/->vec (num/tanh cpu-a))
                  (arr/->vec (num/gelu cpu-a))
                  (arr/->vec (num/matmul cpu-a cpu-b))
                  (arr/->vec cpu-conv)
                  (arr/->vec cpu-norm)
                  (arr/->vec cpu-norm-silu)
                  (arr/->vec cpu-layernorm)
                  (arr/->vec cpu-embedding)
                  (arr/->vec cpu-rmsnorm)
                  (arr/->vec cpu-rope)
                  (arr/->vec cpu-copy-destination)
                  (arr/->vec cpu-slice)
                  (arr/->vec cpu-upsample)
                  (arr/->vec cpu-scaled)
                  [0.0 0.5 1.0]
                  [1.0 3.0 2.0 4.0]
                  (arr/->vec cpu-attention)
                  [1.5 1.5 3.5 3.5]
                  (arr/->vec @(:grad (:q cpu-gradient-result)))
                  (arr/->vec @(:grad (:k cpu-gradient-result)))
                  (arr/->vec @(:grad (:v cpu-gradient-result)))]]
    (-> (gpu/request-device)
        (.then
         (fn [device-result]
           (let [backend (gpu/backend device-result)
                 a (arr/from-vec backend [1.0 2.0 3.0 4.0] [2 2] :f16)
                 b (arr/from-vec backend [0.5 -1.0 2.0 0.25] [2 2] :f16)
                 conv (tensor/conv2d-nchw
                       (arr/from-vec backend conv-input-values [1 2 4 4] :f16)
                       (arr/from-vec backend conv-weight-values [4 2 3 3] :f16)
                       (arr/from-vec backend conv-bias-values [4] :f16)
                       {:padding 1})
                 norm (tensor/group-norm-nchw
                       conv 2
                       (arr/from-vec backend [0.9 1.0 1.1 1.2] [4] :f16)
                       (arr/from-vec backend [0.01 -0.02 0.03 -0.04] [4] :f16)
                       1.0e-5)
                 norm-silu (tensor/group-norm-silu-nchw
                            conv 2
                            (arr/from-vec backend [0.9 1.0 1.1 1.2] [4] :f16)
                            (arr/from-vec backend [0.01 -0.02 0.03 -0.04] [4] :f16)
                            1.0e-5)
                 layernorm (tensor/layer-norm-last
                            a
                            (arr/from-vec backend [0.9 1.1] [2] :f16)
                            (arr/from-vec backend [0.1 -0.2] [2] :f16) 1.0e-5)
                 embedding (tensor/embedding
                            (arr/from-vec backend embedding-indices [4])
                            (arr/from-vec backend embedding-weights [3 2] :f16))
                 rmsnorm (tensor/rms-norm-last
                          a (arr/from-vec backend rms-weight-values [2] :f16))
                 rope (tensor/rotary-embedding a 1 rope-opts)
                 copy-destination (arr/zeros backend [6] :f16)
                 _ (tensor/copy-into! copy-destination
                                      (arr/from-vec backend [0.25 -0.5] [2] :f16) 2)
                 cast-f32 (arr/cast a :f32)
                 cast-back (arr/cast cast-f32 :f16)
                 odd (arr/from-vec backend [1 2 3 4 5] [1 1 1 5] :f16)
                 sliced (tensor/slice-axis odd 3 1 4)
                 upsampled (tensor/upsample-nearest2d
                            (arr/from-vec backend [1 2 3] [1 1 1 3] :f16) [2 2])
                 scaled (tensor/scale odd 0.25)
                 rgb (tensor/nchw-to-rgb-image
                      (arr/from-vec backend [-1 0 1] [1 3 1 1] :f16))
                 transposed (tensor/transpose a [1 0])
                 attention (tensor/multi-head-attention
                            (arr/from-vec backend attention-values [1 2 4] :f16)
                            (arr/from-vec backend attention-values [1 2 4] :f16)
                            (arr/from-vec backend [1 2 3 4, 5 6 7 8] [1 2 4] :f16) 1)
                 biased (tensor/add a (arr/from-vec backend [0.5 -0.5] [2] :f16))
                 [gradient-result gradient-tape]
                 (ag/with-tape
                   (let [q (ag/value (arr/from-vec backend attention-values [1 2 4] :f16))
                         k (ag/value (arr/from-vec backend attention-values [1 2 4] :f16))
                         v (ag/value (arr/from-vec backend [1 2 3 4, 5 6 7 8]
                                                   [1 2 4] :f16))
                         output (ag/multi-head-attention* q k v 1)]
                     {:q q :k k :v v :output output}))
                 gradient-seed (arr/from-vec backend attention-upstream [1 2 4] :f16)
                 backward-baseline (gpu/backend-stats backend)
                 _ (ag/backward! (:output gradient-result)
                                 gradient-seed
                                 gradient-tape)
                 backward-stats (gpu/backend-stats backend)
                 gradient-bytes (reduce + (map #(.-size (:handle %))
                                              [@(:grad (:q gradient-result))
                                               @(:grad (:k gradient-result))
                                               @(:grad (:v gradient-result))]))
                 outputs [(num/add a b) (num/silu a) (num/sigmoid a) (num/tanh a)
                          (num/gelu a)
                          (num/matmul a b) conv norm norm-silu layernorm embedding rmsnorm rope
                          copy-destination sliced upsampled scaled rgb transposed attention biased
                          @(:grad (:q gradient-result)) @(:grad (:k gradient-result))
                          @(:grad (:v gradient-result))
                          cast-f32 cast-back]]
             (println "adapter:" (or (gpu/adapter-description device-result) "unknown"))
             (println "f16 physical bytes:" (.-size (:handle a)))
             (.then
              (js/Promise.all (into-array (map arr/->vec (into [a] outputs))))
              (fn [actual]
                (let [input-values (vec (aget actual 0))
                      actual-values (mapv #(vec (aget actual %)) (range 1 27))
                      _ (println "uploaded:" input-values)
                      checks [(= 8 (.-size (:handle a)))
                              (= 3 (- (:live-buffers backward-stats)
                                      (:live-buffers backward-baseline)))
                              (= gradient-bytes
                                 (- (:live-bytes backward-stats)
                                    (:live-bytes backward-baseline)))
                              (approx-vec? (nth expected 0) (nth actual-values 0) 0.002)
                              (approx-vec? (nth expected 1) (nth actual-values 1) 0.002)
                              (approx-vec? (nth expected 2) (nth actual-values 2) 0.002)
                              (approx-vec? (nth expected 3) (nth actual-values 3) 0.002)
                              (approx-vec? (nth expected 4) (nth actual-values 4) 0.002)
                              (approx-vec? (nth expected 5) (nth actual-values 5) 0.01)
                              (approx-vec? (nth expected 6) (nth actual-values 6) 0.01)
                              (approx-vec? (nth expected 7) (nth actual-values 7) 0.03)
                              (approx-vec? (nth expected 8) (nth actual-values 8) 0.03)
                              (approx-vec? (nth expected 9) (nth actual-values 9) 0.01)
                              (approx-vec? (nth expected 10) (nth actual-values 10) 0.002)
                              (approx-vec? (nth expected 11) (nth actual-values 11) 0.01)
                              (approx-vec? (nth expected 12) (nth actual-values 12) 0.002)
                              (approx-vec? (nth expected 13) (nth actual-values 13) 0.002)
                              (approx-vec? (nth expected 14) (nth actual-values 14) 0.002)
                              (approx-vec? (nth expected 15) (nth actual-values 15) 0.002)
                              (approx-vec? (nth expected 16) (nth actual-values 16) 0.002)
                              (approx-vec? (nth expected 17) (nth actual-values 17) 0.002)
                              (approx-vec? (nth expected 18) (nth actual-values 18) 0.002)
                              (approx-vec? (nth expected 19) (nth actual-values 19) 0.02)
                              (approx-vec? (nth expected 20) (nth actual-values 20) 0.002)
                              (approx-vec? (nth expected 21) (nth actual-values 21) 0.03)
                              (approx-vec? (nth expected 22) (nth actual-values 22) 0.03)
                              (approx-vec? (nth expected 23) (nth actual-values 23) 0.03)
                              (approx-vec? [1.0 2.0 3.0 4.0]
                                           (nth actual-values 24) 0.0001)
                              (approx-vec? [1.0 2.0 3.0 4.0]
                                           (nth actual-values 25) 0.002)]
                      passed (count (filter true? checks))]
                  (println (str "Metal f16: " passed "/" (count checks) " passed"))
                  (when-not (= passed (count checks))
                    (.exit js/Deno 1))))))))
        (.catch
         (fn [error]
           (js/console.error error)
           (.exit js/Deno 1))))))

(set! *main-cli-fn* -main)
