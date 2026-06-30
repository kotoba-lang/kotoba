(ns kotodama.verify.torch-num-smoke
  "Minimal torch-clj graph -> num-clj execution smoke.

  This is not a Gemma loader. It verifies the lowering boundary that Gemma will
  need: a torch-clj graph is executed by a host backend using num-clj tensor
  operations, with deterministic weights supplied by the host."
  (:require [num.array :as arr]
            [num.core :as num]
            [num.cpu :as cpu]
            [kotodama.inference.gemma :as gemma]
            [torch.core :as torch]
            [torch.model :as model]
            [torch.ports :as ports]))

(defn- approx= [a b]
  (< (Math/abs (- (double a) (double b))) 1.0e-6))

(defn- softmax-host [xs]
  (let [m (apply max xs)
        exps (mapv #(Math/exp (- (double %) m)) xs)
        z (reduce + exps)]
    (mapv #(/ % z) exps)))

(defn- linear [backend input in out]
  (let [weights (arr/from-vec backend [1.0 -1.0
                                       0.5 0.25
                                       -0.5 2.0]
                              [in out])
        bias (arr/from-vec backend [0.1 -0.2] [1 out])]
    (num/add (num/matmul input weights) bias)))

(defn num-backend []
  (let [backend (cpu/cpu-backend)]
    (reify ports/IBackend
      (forward [_ graph input]
        (loop [x input
               layers (:torch/layers graph)]
          (if-not (seq layers)
            x
            (let [layer (first layers)
                  ltype (model/layer-type layer)
                  args (model/layer-args layer)]
              (case ltype
                :linear (let [[in out] args]
                          (recur (linear backend x in out) (rest layers)))
                :softmax (recur (arr/from-vec backend (softmax-host (arr/->vec x)) (:shape x))
                                (rest layers))
                (throw (ex-info "unsupported smoke layer"
                                {:torch/layer-type ltype
                                 :torch/layer layer}))))))))))

(defn- add-constant [backend input c]
  (arr/from-vec backend
                 (mapv #(+ (double %) (double c)) (arr/->vec input))
                 (:shape input)))

(defn gemma-block-backend []
  (let [backend (cpu/cpu-backend)]
    (reify ports/IBackend
      (forward [_ graph input]
        (loop [x input
               trace []
               layers (:torch/layers graph)]
          (if-not (seq layers)
            {:output x
             :trace trace}
            (let [layer (first layers)
                  ltype (model/layer-type layer)
                  args (model/layer-args layer)]
              (case ltype
                :gemma4-block
                (let [layer-index (:layer-index args)
                      x* (add-constant backend x (inc layer-index))]
                  (recur x*
                         (conj trace {:layer-type ltype
                                      :layer-index layer-index
                                      :shape (:shape x*)})
                         (rest layers)))

                (throw (ex-info "unsupported Gemma block smoke layer"
                                {:torch/layer-type ltype
                                 :torch/layer layer}))))))))))

(defn -main [& _]
  (let [backend (cpu/cpu-backend)
        graph (model/sequential (model/linear 3 2) (model/softmax))
        input (arr/from-vec backend [2.0 1.0 -1.0] [1 3])
        output (torch/run (num-backend) graph input)
        actual (arr/->vec output)
        logits [(+ (* 2.0 1.0) (* 1.0 0.5) (* -1.0 -0.5) 0.1)
                (+ (* 2.0 -1.0) (* 1.0 0.25) (* -1.0 2.0) -0.2)]
        expected (softmax-host logits)]
    (when-not (and (= [1 2] (:shape output))
                   (every? true? (map approx= actual expected)))
      (throw (ex-info "torch graph did not lower to expected num output"
                      {:actual actual
                       :expected expected
                       :shape (:shape output)})))
    (let [gemma-graph (gemma/gemma4-e4b-graph (assoc gemma/gemma4-e4b-expected
                                                     :gemma4/block-count 2))
          block-graph (model/sequential
                       (nth (:torch/layers gemma-graph) 1)
                       (nth (:torch/layers gemma-graph) 2))
          block-input (arr/from-vec backend [0.0 1.0] [2])
          block-result (torch/run (gemma-block-backend) block-graph block-input)
          block-output (:output block-result)
          block-actual (arr/->vec block-output)]
      (when-not (and (= [2] (:shape block-output))
                     (= [3.0 4.0] block-actual)
                     (= [0 1] (mapv :layer-index (:trace block-result))))
        (throw (ex-info "Gemma block graph did not lower through torch-num backend"
                        {:actual block-actual
                         :shape (:shape block-output)
                         :trace (:trace block-result)})))
      (prn {:kotodama/torch-num-smoke :ok
            :kotodama/model-graph (:torch/module graph)
            :kotodama/input-shape (:shape input)
            :kotodama/output-shape (:shape output)
            :kotodama/output actual
            :kotodama/gemma-block-graph {:block-count 2
                                          :layer-indices (mapv :layer-index (:trace block-result))
                                          :output-shape (:shape block-output)
                                          :output block-actual}}))))
