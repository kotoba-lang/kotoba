(ns kotodama.verify.maturity
  "Static maturity gate for kotodama inference verification assets."
  (:require [clojure.edn :as edn]
            [clojure.java.io :as io]
            [clojure.string :as str]
            [kotodama.inference.gemma :as gemma]
            [kotodama.inference.runtime :as rt]))

(def required-foundation
  {:portable-runtime :torch-transformer
   :model-graph :torch-clj
   :tensor-compute :num-clj})

(def required-gates
  #{:cljc-contract
    :rust-native-build
    :rust-wasm-build
    :num-clj
    :num-cljs
    :num-webgpu
    :num-metal-full-contract
    :torch-clj
    :torch-num-smoke
    :gemma4-e4b-gguf
    :gemma4-e4b-live})

(def banned-foundation-patterns
  [{:id :transformers-js
    :pattern "@huggingface/transformers"}
   {:id :onnx-runtime
    :pattern "onnxruntime"}
   {:id :onnx-runtime-web
    :pattern "ONNX Runtime Web"}
   {:id :onnx-runtime-keyword
    :pattern ":onnx"}])

(defn- fail! [message data]
  (throw (ex-info message data)))

(defn- read-maturity []
  (let [file (io/file "verify/maturity.edn")]
    (when-not (.isFile file)
      (fail! "missing maturity.edn" {:path (.getPath file)}))
    (edn/read-string (slurp file))))

(defn- assert-artifacts! [maturity]
  (let [missing (->> (:required-artifacts maturity)
                     (remove #(.exists (io/file %)))
                     vec)]
    (when (seq missing)
      (fail! "missing required maturity artifacts" {:missing missing}))))

(defn- assert-foundation! [maturity]
  (let [foundation (:foundation maturity)]
    (doseq [[k v] required-foundation]
      (when (not= v (get foundation k))
        (fail! "maturity foundation mismatch" {:key k
                                               :expected v
                                               :actual (get foundation k)})))
    (when (not= #{:torch-transformer} rt/supported-runtimes)
      (fail! "runtime contract includes non-foundation runtimes"
             {:supported-runtimes rt/supported-runtimes}))
    (doseq [backend [:num/wgsl :num/webgpu :num/wasm]]
      (when-not (contains? rt/supported-compute-backends backend)
        (fail! "missing primary num compute backend"
               {:backend backend
                :supported rt/supported-compute-backends})))
    (when-not (contains? (set (:kotodama/direct-lowering-ops (gemma/runtime-spec)))
                         :gguf-tensor-read)
      (fail! "Gemma direct runtime spec is missing GGUF tensor read lowering"
             {:ops (:kotodama/direct-lowering-ops (gemma/runtime-spec))}))))

(defn- assert-gates! [maturity]
  (let [gates (:gates maturity)
        ids (set (map :id gates))
        missing (vec (sort (remove ids required-gates)))
        empty-commands (->> gates
                            (filter #(str/blank? (:command %)))
                            (map :id)
                            vec)]
    (when (seq missing)
      (fail! "missing required maturity gates" {:missing missing}))
    (when (seq empty-commands)
      (fail! "maturity gates require commands" {:gates empty-commands}))))

(defn- source-files []
  (->> ["cljc/src" "cljc/test" "browser"]
       (map io/file)
       (filter #(.exists %))
       (mapcat file-seq)
       (filter #(.isFile %))
       (remove #(str/starts-with? (.getPath %) "verify/out/"))))

(defn- assert-non-foundations-absent! [_maturity]
  (let [matches (for [file (source-files)
                      banned banned-foundation-patterns
                      :let [text (slurp file)]
                      :when (str/includes? text (:pattern banned))]
                  {:file (.getPath file)
                   :banned (:id banned)
                   :pattern (:pattern banned)})]
    (when (seq matches)
      (fail! "non-foundation runtime dependency leaked into kotodama inference surface"
             {:matches (vec matches)}))))

(defn -main [& _]
  (let [maturity (read-maturity)]
    (assert-artifacts! maturity)
    (assert-foundation! maturity)
    (assert-gates! maturity)
    (assert-non-foundations-absent! maturity)
    (prn {:kotodama/maturity :ok
          :kotodama/scope (:scope maturity)
          :kotodama/gates (mapv :id (:gates maturity))
          :kotodama/known-gaps (mapv :id (:known-gaps maturity))})))
