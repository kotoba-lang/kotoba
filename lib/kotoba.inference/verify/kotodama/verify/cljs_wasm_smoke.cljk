(ns kotodama.verify.cljs-wasm-smoke
  "CLJS terminal smoke for the kotodama wasm inference surface.

  This proves the portable path that kotoba wasm/browser hosts need:
  IModelRuntime -> kotodama.inference.core/forward/generate -> torch/run ->
  num-clj tensor ops. Real GGUF/WebGPU execution is still covered by separate
  local-model and host GPU gates."
  (:require [kotodama.inference.core :as inference]
            [kotodama.inference.ports :as inference-ports]
            [kotodama.inference.runtime :as runtime]
            [num.array :as arr]
            [num.core :as num]
            [num.cpu :as cpu]
            [torch.core :as torch]
            [torch.model :as model]
            [torch.ports :as torch-ports]))

(defn- approx= [a b]
  (< (js/Math.abs (- (double a) (double b))) 1.0e-6))

(defn- softmax-host [xs]
  (let [m (apply max xs)
        exps (mapv #(js/Math.exp (- (double %) m)) xs)
        z (reduce + exps)]
    (mapv #(/ % z) exps)))

(defn- token-features [token-ids]
  (let [ids (vec token-ids)
        n (count ids)
        sum-ids (reduce + 0 ids)
        last-id (or (peek ids) 0)]
    [(double sum-ids) (double n) (double last-id)]))

(defn- fixed-linear [backend input in out]
  (let [weights (arr/from-vec backend [0.10 -0.20 0.05 0.00
                                       0.00 0.10 -0.10 0.20
                                       0.30 0.00 0.15 -0.05]
                              [in out])
        bias (arr/from-vec backend [0.01 -0.02 0.03 0.00] [1 out])]
    (num/add (num/matmul input weights) bias)))

(defn- torch-num-backend []
  (let [backend (cpu/cpu-backend)]
    (reify torch-ports/IBackend
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
                :linear
                (let [[in out] args
                      x* (fixed-linear backend x in out)]
                  (recur x*
                         (conj trace {:layer-type ltype
                                      :shape (:shape x*)})
                         (rest layers)))

                :softmax
                (let [x* (arr/from-vec backend
                                       (softmax-host (arr/->vec x))
                                       (:shape x))]
                  (recur x*
                         (conj trace {:layer-type ltype
                                      :shape (:shape x*)})
                         (rest layers)))

                (throw (js/Error. (str "unsupported cljs wasm smoke layer: " ltype)))))))))))

(defn- argmax-index [xs]
  (first
   (reduce (fn [[best-i best-v] [i v]]
             (if (> v best-v) [i v] [best-i best-v]))
           [0 (first xs)]
           (map-indexed vector xs))))

(defn- wasm-smoke-runtime []
  (let [backend (cpu/cpu-backend)
        sessions (atom {})]
    (inference-ports/fn-runtime
     {:probe (fn []
               {:kotodama/backends [:wasm]
                :kotodama/compute-backends [:num/wasm :num/cpu]
                :kotodama/forward [:cljs :torch-run :num]})
      :load (fn [runtime-spec]
              (let [session {:kotodama/session-id (str "cljs-wasm-smoke-" (count @sessions))
                             :kotodama/runtime (:kotodama/runtime runtime-spec)
                             :kotodama/model (:kotodama/model runtime-spec)
                             :kotodama/backend (:kotodama/backend runtime-spec)
                             :kotodama/compute-backend (:kotodama/compute-backend runtime-spec)
                             :kotodama/model-graph (:kotodama/model-graph runtime-spec)}]
                (swap! sessions assoc (:kotodama/session-id session) session)
                session))
      :forward (fn [session token-ids _options]
                 (let [input (arr/from-vec backend (token-features token-ids) [1 3])
                       run (torch/run (torch-num-backend)
                                      (:kotodama/model-graph session)
                                      input)
                       output (:output run)
                       logits (arr/->vec output)]
                   {:kotodama/forward :cljs-wasm-torch-num
                    :kotodama/input-ids (vec token-ids)
                    :kotodama/logits logits
                    :kotodama/greedy-token-id (argmax-index logits)
                    :kotodama/output-shape (:shape output)
                    :torch/trace (:trace run)}))
      :generate (fn [session token-ids generation]
                  (let [max-new (:kotodama/max-new-tokens generation 1)]
                    (loop [ids (vec token-ids)
                           produced []]
                      (if (= (count produced) max-new)
                        {:kotodama/generated-token-ids produced
                         :kotodama/token-ids ids}
                        (let [result (inference/forward
                                      (wasm-smoke-runtime)
                                      session
                                      ids)
                              next-id (:kotodama/greedy-token-id result)]
                          (recur (conj ids next-id)
                                 (conj produced next-id)))))))
      :dispose (fn [session]
                 (swap! sessions dissoc (:kotodama/session-id session))
                 {:kotodama/disposed? true
                  :kotodama/session-id (:kotodama/session-id session)})})))

(defn- expected-forward [token-ids]
  (let [[sum-ids n last-id] (token-features token-ids)
        logits [(+ (* sum-ids 0.10) (* n 0.00) (* last-id 0.30) 0.01)
                (+ (* sum-ids -0.20) (* n 0.10) (* last-id 0.00) -0.02)
                (+ (* sum-ids 0.05) (* n -0.10) (* last-id 0.15) 0.03)
                (+ (* sum-ids 0.00) (* n 0.20) (* last-id -0.05) 0.00)]]
    (softmax-host logits)))

(defn -main [& _]
  (let [runtime* (wasm-smoke-runtime)
        graph (model/sequential (model/linear 3 4) (model/softmax))
        spec (runtime/transformer "cljs-wasm-smoke"
                                  {:kotodama/backend :wasm
                                   :kotodama/compute-backend :num/wasm
                                   :kotodama/model-graph graph})
        session (inference/load-model runtime* spec)
        token-ids [2 1 3]
        forward (inference/forward runtime* session token-ids)
        expected (expected-forward token-ids)
        generated (inference/generate runtime* session token-ids
                                      {:kotodama/max-new-tokens 2})
        disposed (inference/dispose runtime* session)]
    (when-not (and (= [1 4] (:kotodama/output-shape forward))
                   (every? true? (map approx= (:kotodama/logits forward) expected))
                   (= [:linear :softmax] (mapv :layer-type (:torch/trace forward))))
      (throw (js/Error. (str "cljs wasm forward smoke failed "
                             (pr-str {:forward forward
                                      :expected expected})))))
    (when-not (and (= 2 (count (:kotodama/generated-token-ids generated)))
                   (= 5 (count (:kotodama/token-ids generated)))
                   (:kotodama/disposed? disposed))
      (throw (js/Error. (str "cljs wasm generate smoke failed "
                             (pr-str {:generated generated
                                      :disposed disposed})))))
    (prn {:kotodama/cljs-wasm-smoke :ok
          :kotodama/backend :wasm
          :kotodama/compute-backend :num/wasm
          :kotodama/forward (:kotodama/forward forward)
          :kotodama/output-shape (:kotodama/output-shape forward)
          :kotodama/logits (:kotodama/logits forward)
          :kotodama/generated-token-ids (:kotodama/generated-token-ids generated)
          :torch/trace (:torch/trace forward)})))

(set! *main-cli-fn* -main)
