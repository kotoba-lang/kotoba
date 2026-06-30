(ns kotodama.inference.core-test
  (:require [kotodama.inference.core :as core]
            [kotodama.inference.gemma :as gemma]
            [kotodama.inference.ports :as ports]
            [kotodama.inference.runtime :as rt]
            [kotodama.inference.validate :as validate]
            #?(:clj [clojure.test :refer [deftest is testing]]
               :cljs [cljs.test :refer-macros [deftest is testing]])))

(defn mock-runtime []
  (let [sessions (atom {})]
    (ports/fn-runtime
      {:probe (fn [] {:kotodama/backends [:webgpu :webgl :wasm]})
       :load (fn [spec]
               (let [session {:kotodama/session-id (str "s-" (count @sessions))
                              :kotodama/runtime (:kotodama/runtime spec)
                              :kotodama/backend (:kotodama/backend spec)
                              :kotodama/spec spec}]
                 (swap! sessions assoc (:kotodama/session-id session) session)
                 session))
       :generate (fn [session input generation]
                   {:kotodama/text (str (:kotodama/session-id session) ":" input)
                    :kotodama/generation generation})
       :forward (fn [session token-ids _]
                  {:kotodama/session-id (:kotodama/session-id session)
                   :kotodama/logits [(count token-ids)]})
       :dispose (fn [session]
                  (swap! sessions dissoc (:kotodama/session-id session))
                  {:kotodama/disposed? true})})))

(deftest runtime-specs-are-data
  (testing "decoder transformer runtime"
    (let [spec (rt/transformer "tiny-random-gpt2")]
      (is (= :torch-transformer (:kotodama/runtime spec)))
      (is (= :num/wgsl (:kotodama/compute-backend spec)))
      (is (= :sequential (:torch/module (:kotodama/model-graph spec)))))))

(deftest gemma4-direct-runtime-spec-is-data
  (let [spec (gemma/runtime-spec)
        graph (:kotodama/model-graph spec)
        layer-types (map (comp first keys) (:torch/layers graph))
        block-layers (filter #(= :gemma4-block (first (keys %))) (:torch/layers graph))
        ops (:kotodama/direct-lowering-ops spec)]
    (is (= :torch-transformer (:kotodama/runtime spec)))
    (is (= "gemma4:e4b" (:kotodama/model spec)))
    (is (= :gemma4 (:kotodama/model-family spec)))
    (is (= :gguf (:kotodama/artifact-format spec)))
    (is (= :sequential (:torch/module graph)))
    (is (= (:gemma4/block-count gemma/gemma4-e4b-expected) (count block-layers)))
    (is (some #{:gemma4-block} layer-types))
    (is (= 0 (get-in (first block-layers) [:gemma4-block :layer-index])))
    (is (= 41 (get-in (last block-layers) [:gemma4-block :layer-index])))
    (is (every? (set ops) gemma/required-direct-lowering-ops))
    (is (gemma/direct-ready? {:kotodama/direct-lowering-ops ops}))
    (is (not (gemma/direct-ready? {:kotodama/direct-lowering-ops [:tokenize]})))
    (is (= [2560 262144]
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/required-tensors "token_embd.weight" :shape])))
    (is (= [2560 10240]
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/required-tensors "blk.0.ffn_gate.weight" :shape])))
    (is (= [10240 2560]
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/required-tensors "blk.0.ffn_down.weight" :shape])))
    (is (= {0 1501 1 116 12 339 14 41 30 134}
           (:gguf/tensor-type-counts gemma/gemma4-e4b-expected)))
    (is (= 1000000.0 (:gemma4/rope-freq-base gemma/gemma4-e4b-expected)))
    (is (= 10000.0 (:gemma4/rope-freq-base-swa gemma/gemma4-e4b-expected)))
    (is (= 10240
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/expected-tensor-spans "output_norm.weight"])))
    (is (= [7.90625 8.25 4.125 7.5625 8.9375 8.8125 7.59375 8.8125]
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/f32-samples "output_norm.weight"])))
    (is (= [6.59375 6.5 0.92578125 0.68359375 5.875 6.4375 5.84375 4.21875]
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/f32-samples "blk.0.ffn_norm.weight"])))
    (is (= {:block 0
            :value-count 256
            :sample [-0.025895 0.026871 -0.043484 0.026871
                     -0.008306 0.026871 0.026871 0.04446
                     0.04446 -0.043484 0.04446 -0.008306
                     0.026871 0.009283 -0.078662 0.026871]
            :sum 0.216478
            :min -0.096251
            :max 0.167582}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/q4-k-samples "blk.0.attn_q.weight"])))
    (is (= {:block 0
            :value-count 256
            :sample [-0.088019 0.021704 0.010732 -2.4E-4
                     -0.022185 -2.4E-4 -0.011213 -0.04413
                     -0.033157 -0.022185 -0.033157 0.021704
                     -2.4E-4 -0.011213 -0.022185 -0.022185]
            :sum -0.189283
            :min -0.088019
            :max 0.088834}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/q4-k-samples "blk.0.attn_output.weight"])))
    (is (= {:block 0
            :value-count 256
            :sample [-0.018165 -0.011 0.017659 -0.025329
                     -0.032494 0.053483 0.010494 -0.011
                     -0.003835 0.00333 0.024824 -0.011
                     -0.018165 -0.025329 0.010494 0.00333]
            :sum -0.285571
            :min -0.060202
            :max 0.075613}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/q4-k-samples "blk.0.ffn_gate.weight"])))
    (is (= {:block 0
            :value-count 256
            :sample [0.004841 0.013312 -0.009682 -0.026625
                     -0.00242 0.0 -0.003631 0.037517
                     -0.003631 -0.026625 0.038727 0.00242
                     0.00121 0.020574 0.022994 0.012102]
            :sum 0.212123
            :min -0.068848
            :max 0.053249}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/q6-k-samples "blk.0.ffn_down.weight"])))
    (is (= {:block 0
            :value-count 256
            :sample [-0.034324 0.005536 0.029895 -0.007751
                     0.007751 -0.022144 0.006643 0.01993
                     0.028788 0.022144 0.011072 -0.006643
                     0.014394 0.004429 -0.002214 0.028788]
            :sum -0.213976
            :min -0.051086
            :max 0.050674}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/q6-k-samples "token_embd.weight"])))
    (is (= {:token-id 2
            :value-count 2560
            :sample [-0.028427 0.055078 0.030204 0.033757
                     -0.044417 -0.031981 0.023097 0.024874
                     -0.014214 0.049747 0.014214 -0.046194
                     -0.017767 -0.012437 0.035534 -0.003553]
            :sum -3.432013
            :min -0.098152
            :max 0.084961}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/token-embedding-samples 2])))
    (is (= {:value-count 2560
            :sample [-9.542505 19.018743 13.227827 12.103419
                     -14.910164 -10.427495 7.753285 8.978163
                     -4.429227 15.981131 4.617341 -14.95078
                     -5.643417 -5.506607 14.450568 -1.175712]
            :sum -1463.854214
            :min -147.408141
            :max 113.803208}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/rmsnorm-samples :blk.0/attn_norm])))
    (is (= {:value-count 2560
            :sample [-9.74772 19.615149 5.95979 11.128647
                     -16.994381 -12.082043 7.642127 9.397144
                     -4.925164 9.217581 4.890961 -16.896048
                     -6.284714 -4.279591 12.654935 -1.274044]
            :sum -1184.465932
            :min -36.845099
            :max 29.337727}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/rmsnorm-samples :output/norm])))
    (is (= {:value-count 2560
            :sample [-8.311214 15.904175 2.239464 2.18816
                     -11.757119 -9.157727 6.085912 4.997844
                     -4.035898 4.548936 4.070101 -3.042956
                     -2.330047 -3.785792 12.056391 -0.163798]
            :sum -972.988346
            :min -45.702691
            :max 39.935647}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/rmsnorm-samples :blk.0/ffn_norm])))
    (is (= {:rows [0 1 2 3]
            :value-count 4
            :sample [-45.52616 -9.02556 17.067708 10.863354]
            :sum -26.620658
            :min -45.52616
            :max 17.067708}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/projection-samples :blk.0/attn_q])))
    (is (= {:rows [0 1 2 3]
            :value-count 4
            :sample [2.762013 5.861241 1.781327 -12.989838]
            :sum -2.585257
            :min -12.989838
            :max 5.861241}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/projection-samples :blk.0/attn_k])))
    (is (= {:rows [0 1 2 3]
            :value-count 4
            :sample [12.377182 6.985937 -25.919527 -9.185445]
            :sum -15.741853
            :min -25.919527
            :max 12.377182}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/projection-samples :blk.0/attn_v])))
    (is (= {:position 1
            :rope-dim 512
            :theta 1000000.0
            :value-count 4
            :sample [-17.003142 -43.185473 1.142816 20.199334]
            :sum -38.846467
            :min -43.185473
            :max 20.199334}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/rope-samples :blk.0/attn_q])))
    (is (= {:position 1
            :rope-dim 512
            :theta 1000000.0
            :value-count 4
            :sample [-3.439742 5.490996 11.586776 -6.136419]
            :sum 7.501611
            :min -6.136419
            :max 11.586776}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/rope-samples :blk.0/attn_k])))
    (is (= {:head 0
            :position 1
            :rows [0 255]
            :rope? true
            :value-count 256
            :sample [-17.003142 -43.185473 1.142816 20.199334
                     8.733221 -1.21323 25.764199 -6.928831
                     12.818862 -6.840196 9.592058 3.057451
                     10.090412 31.378267 -39.082596 -10.293496]
            :sum 507.18331
            :min -47.277438
            :max 46.409391}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/head-samples :blk.0/attn_q])))
    (is (= {:kv-head 0
            :position 1
            :rows [0 255]
            :rope? true
            :value-count 256
            :sample [-3.439742 5.490996 11.586776 -6.136419
                     -5.520219 -10.766966 -11.001778 -10.644984
                     -14.205547 -9.792202 14.644115 36.676927
                     -20.806993 14.045396 -1.463094 7.666998]
            :sum -234.295058
            :min -125.756052
            :max 105.184306}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/head-samples :blk.0/attn_k])))
    (is (= {:q-head 0
            :kv-head 0
            :position 1
            :head-dim 256
            :weights [1.0]
            :value-count 256
            :sample [12.377182 6.985937 -25.919527 -9.185445
                     6.495511 9.778855 16.428084 34.7449
                     -2.633967 -33.338899 -20.009645 -7.045471
                     -13.946964 -18.699881 -28.990102 -7.560946]
            :sum 618.697992
            :min -105.957329
            :max 524.540105
            :score 858.776549}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/attention-samples :blk.0/head0-token0])))
    (is (= {:q-head-range [0 7]
            :kv-head-range [0 1]
            :position 1
            :head-dim 256
            :weights [1.0]
            :kv-heads [0 0 0 0 1 1 1 1]
            :value-count 2048
            :sample [12.377182 6.985937 -25.919527 -9.185445
                     6.495511 9.778855 16.428084 34.7449
                     -2.633967 -33.338899 -20.009645 -7.045471
                     -13.946964 -18.699881 -28.990102 -7.560946]
            :sum 1308.781106
            :min -105.957329
            :max 524.540105
            :score-sample [858.776549 300.269659 3052.038987 447.712963
                           3938.141916 3307.641934 1107.97142 2448.466657]
            :score-sum 15461.020084
            :score-min 300.269659
            :score-max 3938.141916}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/attention-samples :blk.0/all-heads-token0])))
    (is (= {:token-ids [2 1]
            :query-token-index 1
            :position 2
            :visible-token-count 2
            :q-head-range [0 7]
            :kv-head-range [0 1]
            :head-dim 256
            :kv-heads [0 0 0 0 1 1 1 1]
            :value-count 2048
            :sample [12.377182 6.985937 -25.919527 -9.185445
                     6.495511 9.778855 16.428084 34.7449
                     -2.633967 -33.338899 -20.009645 -7.045471
                     -13.946964 -18.699881 -28.990102 -7.560946]
            :sum 1715.92625
            :min -105.957329
            :max 524.540105
            :score-sample [[3455.861546 3313.913438]
                           [2602.339283 2360.228822]
                           [2557.991626 3072.474513]
                           [2189.928838 2384.24292]
                           [6915.793803 8040.400481]
                           [6594.745858 7642.837974]
                           [7306.160567 8377.675052]
                           [5790.5647 8021.439567]]
            :weight-sample [[1.0 0.0]
                            [1.0 0.0]
                            [0.0 1.0]
                            [0.0 1.0]
                            [0.0 1.0]
                            [0.0 1.0]
                            [0.0 1.0]
                            [0.0 1.0]]
            :score-sum 80626.598989
            :score-min 2189.928838
            :score-max 8377.675052}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/attention-samples :blk.0/all-heads-token1-causal])))
    (is (= {:rows [0 1 2 3]
            :value-count 4
            :sample [-29.722004 -23.17544 16.067558 14.977672]
            :sum -21.852214
            :min -29.722004
            :max 16.067558}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/attention-output-samples :blk.0/attn_output])))
    (is (= {:row-range [0 2559]
            :row-count 2560
            :value-count 2560
            :sample [-29.722004 -23.17544 16.067558 14.977672
                     4.141382 3.138767 3.956998 -16.81225
                     -4.993406 3.892514 9.3593 3.76334
                     13.311811 11.999482 0.219737 7.77573]
            :sum 172.844843
            :min -123.386853
            :max 204.681356}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/attention-output-samples :blk.0/attn_output_full])))
    (is (= {:row-range [0 2559]
            :row-count 2560
            :value-count 2560
            :sample [-19.385777 -16.479798 12.116745 86.31488
                     -35.930654 -42.579809 11.631068 7.986794
                     8.451271 22.938344 20.931656 8.726331
                     28.811372 -15.041754 -4.533569 -38.74554]
            :sum 674.633087
            :min -568.725398
            :max 954.891269}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/attention-output-samples :blk.0/attn_output_all_heads])))
    (is (= {:rows [0 1 2 3]
            :value-count 4
            :sample [-0.006471 9.23E-4 0.008267 -6.27E-4]
            :sum 0.002091
            :min -0.006471
            :max 0.008267}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/mlp-samples :blk.0/ffn_activation])))
    (is (= {:rows [0 1 2 3]
            :value-count 4
            :sample [-8.2E-5 2.98E-4 2.93E-4 -1.4E-4]
            :sum 3.68E-4
            :min -1.4E-4
            :max 2.98E-4}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/mlp-samples :blk.0/ffn_down])))
    (is (= {:row-range [0 10239]
            :row-count 10240
            :value-count 10240
            :sample [-8.309769 -10.082826 -10.458492 -12.436209
                     6.526065 -4.987348 -5.093058 -8.328873
                     1.228039 -21.997309 -12.25703 -22.912539
                     -7.552858 6.428225 0.854976 -2.12139]
            :sum -61803.077322
            :min -48.908104
            :max 142.473424}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/mlp-samples :blk.0/ffn_gate_full])))
    (is (= {:row-range [0 10239]
            :row-count 10240
            :value-count 10240
            :sample [3.164884 -2.190473 -27.537988 12.701362
                     0.065879 -10.203591 2.003726 4.170693
                     0.884263 -9.882534 -3.69524 -14.573461
                     3.800095 -6.046821 3.393646 2.729366]
            :sum 159.154494
            :min -133.398441
            :max 79.237713}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/mlp-samples :blk.0/ffn_up_full])))
    (is (= {:row-range [0 10239]
            :row-count 10240
            :value-count 10240
            :sample [-0.006471 9.23E-4 0.008267 -6.27E-4
                     0.429302 0.344899 -0.062269 -0.008385
                     0.839924 0.0 2.15E-4 0.0
                     -0.015049 -38.807641 2.035711 -0.619739]
            :sum -13226.405841
            :min -19005.732668
            :max 3113.508802}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/mlp-samples :blk.0/ffn_activation_full])))
    (is (= {:row-range [0 2559]
            :row-count 2560
            :value-count 2560
            :sample [-325.914054 5.66649 745.384302 301.489546
                     34.901631 374.543236 -57.261796 -369.121555
                     -638.696384 145.609252 1016.571174 982.759883
                     -120.902103 -1426.5082 310.331744 665.175388]
            :sum -16264.364623
            :min -1952.473832
            :max 2437.597269}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/mlp-samples :blk.0/ffn_down_full])))
    (is (= [-19.414204 -16.42472 12.146949 86.348638
            -35.975072 -42.61179 11.654165 8.011668
            8.437058 22.988091 20.945869 8.680137
            28.793605 -15.05419 -4.498035 -38.749093]
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/block-samples :blk.0/block0_full :attention-residual :sample])))
    (is (= {:token-ids [1 2 3 4]
            :value-count 4
            :sample [-21.50351 12.06829 15.421071 17.125854]
            :sum 23.111705
            :min -21.50351
            :max 17.125854
            :greedy-token-id 4
            :greedy-logit 17.125854}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/block-samples :blk.0/block0_full :logits])))
    (is (= [21.786053 -13.170049 -0.048589 -0.096977
            26.311274 12.255456 49.101642 -20.358861
            50.512567 -17.410559 20.246101 18.116765
            28.716184 -22.780965 17.584852 44.937288]
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/multi-layer-block-samples :blk.1/block1_full :attention :sample])))
    (is (= {:token-ids [1 2 3 4]
            :value-count 4
            :sample [-14.713764 2.465819 3.89823 12.240504]
            :sum 3.890789
            :min -14.713764
            :max 12.240504
            :greedy-token-id 4
            :greedy-logit 12.240504}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/multi-layer-block-samples :blk.1/block1_full :logits])))
    (is (= {:token-ids [1 2 3 4]
            :value-count 4
            :sample [44.15111 579.290428 29.142786 19.768841]
            :sum 672.353165
            :min 19.768841
            :max 579.290428
            :greedy-token-id 2
            :greedy-logit 579.290428}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/output-logit-samples :token_embd/candidates])))
    (is (= {:token-id-range [0 262143]
            :value-count 262144
            :sample [27.729826 44.15111 579.290428 29.142786
                     19.768841 18.611226 11.031361 8.567112
                     -0.634776 -6.818355 14.057829 24.598353
                     4.391335 -1.881607 17.838161 -2.082648]
            :sum 3231214.589737
            :min -42.362666
            :min-token-id 3104
            :max 579.290428
            :max-token-id 2
            :greedy-token-id 2
            :greedy-logit 579.290428
            :top-k [{:token-id 2 :logit 579.290428}
                    {:token-id 93163 :logit 66.902076}
                    {:token-id 255271 :logit 65.799499}
                    {:token-id 230236 :logit 64.580503}
                    {:token-id 232009 :logit 62.16587}
                    {:token-id 222557 :logit 61.881457}
                    {:token-id 120047 :logit 61.448553}
                    {:token-id 115 :logit 61.233008}
                    {:token-id 233449 :logit 60.473853}
                    {:token-id 117709 :logit 59.999999}
                    {:token-id 162978 :logit 59.466545}
                    {:token-id 220153 :logit 59.278312}
                    {:token-id 112 :logit 59.062668}
                    {:token-id 215641 :logit 58.976559}
                    {:token-id 208478 :logit 58.327678}
                    {:token-id 111 :logit 58.239818}]}
           (get-in gemma/gemma4-e4b-expected
                   [:gguf/output-logit-samples :token_embd/full-vocab])))))

(deftest validation-routes-through-num-backends
  (is (empty? (validate/runtime-problems
                (rt/transformer "m" {:kotodama/backend :webgpu
                                     :kotodama/compute-backend :num/wgsl}))))
  (is (seq (validate/runtime-problems
             (rt/transformer "m" {:kotodama/backend :webgpu
                                  :kotodama/compute-backend :num/cpu}))))
  (is (empty? (validate/runtime-problems
                (rt/transformer "m" {:kotodama/backend :webgl
                                     :kotodama/compute-backend :num/webgl})))))

(deftest core-load-generate-forward
  (let [runtime (mock-runtime)
        session (core/load-model runtime (rt/transformer "tiny"))]
    (is (= [:webgpu :webgl :wasm] (:kotodama/backends (core/probe runtime))))
    (is (= "s-0:hello" (:kotodama/text (core/generate runtime session "hello"))))
    (is (= [3] (:kotodama/logits (core/forward runtime session [1 2 3]))))
    (is (:kotodama/disposed? (core/dispose runtime session)))))

(deftest llm-infer-matches-kototama-host-shape
  (let [runtime (mock-runtime)
        session (core/load-model runtime (rt/transformer "model-a"))]
    (is (= "s-0:ping"
           (:kotodama/text
            (core/llm-infer runtime (constantly session) "model-a" "ping"
                            {:kotodama/max-new-tokens 8}))))))
