(ns kotodama.inference.validate
  (:require [kotodama.inference.runtime :as runtime]))

(defn- problem [code message data]
  (merge {:kotodama/severity :error
          :kotodama/code code
          :kotodama/message message}
         data))

(defn runtime-problems [runtime-spec]
  (let [rt (:kotodama/runtime runtime-spec)
        backend (:kotodama/backend runtime-spec)
        compute-backend (:kotodama/compute-backend runtime-spec)]
    (cond-> []
      (not (contains? runtime/supported-runtimes rt))
      (conj (problem :runtime/unsupported "unsupported runtime"
                     {:kotodama/runtime rt}))

      (not (contains? runtime/supported-backends backend))
      (conj (problem :backend/unsupported "unsupported backend"
                     {:kotodama/backend backend}))

      (not (contains? runtime/supported-compute-backends compute-backend))
      (conj (problem :compute-backend/unsupported "unsupported num-clj compute backend"
                     {:kotodama/compute-backend compute-backend}))

      (and (= rt :torch-transformer) (= backend :webgpu) (not= compute-backend :num/wgsl)
           (not= compute-backend :num/webgpu))
      (conj (problem :compute-backend/not-webgpu
                     "WebGPU transformer runtime should use num-clj WGSL/WebGPU compute"
                     {:kotodama/backend backend
                      :kotodama/compute-backend compute-backend}))

      (and (= rt :torch-transformer) (= backend :webgl) (not= compute-backend :num/webgl))
      (conj (problem :compute-backend/not-webgl
                     "WebGL transformer runtime requires a host-provided num-clj WebGL backend"
                     {:kotodama/backend backend
                      :kotodama/compute-backend compute-backend}))

      (and (= rt :torch-transformer) (empty? (:kotodama/model runtime-spec)))
      (conj (problem :model/missing "torch-transformer runtime requires :kotodama/model" {}))

      (and (= rt :torch-transformer) (nil? (:kotodama/model-graph runtime-spec)))
      (conj (problem :model-graph/missing
                     "torch-transformer runtime requires a torch-clj :kotodama/model-graph"
                     {})))))

(defn generation-problems [generation]
  (let [max-new (:kotodama/max-new-tokens generation)]
    (cond-> []
      (and max-new (or (not (integer? max-new)) (neg? max-new)))
      (conj (problem :generation/max-new-tokens
                     ":kotodama/max-new-tokens must be a non-negative integer"
                     {:kotodama/max-new-tokens max-new})))))

(defn problems [op]
  (case (:kotodama/op op)
    :load (runtime-problems (:kotodama/runtime-spec op))
    :generate (generation-problems (:kotodama/generation op))
    :llm-infer (generation-problems (:kotodama/generation op))
    :forward []
    [(problem :op/unsupported "unsupported inference op" {:kotodama/op (:kotodama/op op)})]))

(defn valid? [op]
  (not-any? #(= :error (:kotodama/severity %)) (problems op)))
