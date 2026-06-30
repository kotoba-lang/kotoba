(ns kotodama.inference.runtime
  "Portable .cljc model-runtime data. This is the kotodama equivalent of the
  public surface people normally reach for through model runtimes: model,
  session, generate, and forward are plain EDN maps. Model graphs are torch-clj
  data; tensor execution is num-clj over an injected backend such as WGSL/WebGPU."
  (:require [torch.model :as torch]))

(def supported-backends #{:webgpu :webgl :wasm :native})
(def supported-runtimes #{:torch-transformer})
(def supported-compute-backends #{:num/cpu :num/wgsl :num/webgpu :num/webgl :num/wasm :num/native})

(def default-generation
  {:kotodama/max-new-tokens 64
   :kotodama/do-sample? false})

(defn normalize-backend [backend]
  (let [b (keyword (or backend :webgpu))]
    (if (contains? supported-backends b)
      b
      (throw (ex-info (str "unsupported inference backend: " backend)
                      {:kotodama/backend backend})))))

(defn generation
  "Generation options as data. Keys stay namespaced so hosts can map them to
  their local decoder implementation."
  ([] default-generation)
  ([opts] (merge default-generation opts)))

(defn normalize-compute-backend [backend]
  (let [b (keyword (or backend :num/wgsl))]
    (if (contains? supported-compute-backends b)
      b
      (throw (ex-info (str "unsupported compute backend: " backend)
                      {:kotodama/compute-backend backend})))))

(defn transformer-block
  "A torch-clj EDN approximation of a decoder transformer block. It is a graph
  contract, not a fused kernel: hosts lower these layer names to num-clj ops or
  custom torch layers."
  [{:keys [hidden-size intermediate-size vocab-size]
    :or {hidden-size 768 intermediate-size 3072 vocab-size 50257}}]
  (torch/sequential
    (torch/embedding vocab-size hidden-size)
    (torch/layernorm hidden-size)
    (torch/layer :causal-self-attention {:hidden-size hidden-size})
    (torch/layernorm hidden-size)
    (torch/linear hidden-size intermediate-size)
    (torch/gelu)
    (torch/linear intermediate-size hidden-size)
    (torch/layernorm hidden-size)
    (torch/linear hidden-size vocab-size)
    (torch/softmax)))

(defn transformer
  "A decoder-transformer text runtime spec backed by torch-clj model data and
  num-clj compute. Browser WebGPU hosts should bind `:num/wgsl` or
  `:num/webgpu`; native hosts may bind native num backends. WebGL is kept as a
  host compatibility target, but the portable primary path is WGSL/WebGPU."
  ([model] (transformer model {}))
  ([model opts]
   (let [backend (normalize-backend (:kotodama/backend opts :webgpu))
         compute-backend (normalize-compute-backend (:kotodama/compute-backend opts :num/wgsl))
         model-graph (or (:kotodama/model-graph opts)
                         (transformer-block {:hidden-size (:kotodama/hidden-size opts 768)
                                             :intermediate-size (:kotodama/intermediate-size opts 3072)
                                             :vocab-size (:kotodama/vocab-size opts 50257)}))]
     (merge {:kotodama/runtime :torch-transformer
             :kotodama/model model
             :kotodama/task (:kotodama/task opts :text-generation)
             :kotodama/backend backend
             :kotodama/compute-backend compute-backend
             :kotodama/model-graph model-graph}
            (select-keys opts [:kotodama/dtype
                               :kotodama/revision
                               :kotodama/cache-dir
                               :kotodama/local-files-only?
                               :kotodama/tokenizer])))))

(defn load-op [runtime-spec]
  {:kotodama/op :load
   :kotodama/runtime-spec runtime-spec})

(defn generate-op
  ([session prompt-or-token-ids] (generate-op session prompt-or-token-ids {}))
  ([session prompt-or-token-ids opts]
   {:kotodama/op :generate
    :kotodama/session session
    :kotodama/input prompt-or-token-ids
    :kotodama/generation (generation opts)}))

(defn forward-op
  ([session token-ids] (forward-op session token-ids {}))
  ([session token-ids opts]
   {:kotodama/op :forward
    :kotodama/session session
    :kotodama/input-ids (vec token-ids)
    :kotodama/options opts}))

(defn kototama-infer-op
  "The data shape behind kototama's `(llm-infer model prompt)` capability."
  ([model prompt] (kototama-infer-op model prompt {}))
  ([model prompt opts]
   {:kotodama/op :llm-infer
    :kotodama/model model
    :kotodama/prompt prompt
    :kotodama/generation (generation opts)}))
