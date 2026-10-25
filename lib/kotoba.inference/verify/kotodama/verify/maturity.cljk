(ns kotodama.verify.maturity
  "Static maturity gate for kotodama inference verification assets."
  (:require [clojure.edn :as edn]
            [clojure.java.io :as io]
            [kotoba.lang.text :as str]
            [kotodama.inference.gemma :as gemma]
            [kotodama.inference.runtime :as rt]))

(def required-foundation
  {:portable-runtime :torch-transformer
   :model-graph :torch-clj
   :tensor-compute :num-clj})

(def required-gates
  #{:cljc-contract
    :num-clj
    :num-cljs
    :num-webgpu
    :num-metal-full-contract
    :torch-clj
    :torch-num-smoke
    :cljs-wasm-smoke
    :gemma4-e4b-gguf
    ;; ⚠ `:gemma4-e4b-live` LEFT THIS SET on 2026-09-09, and it is the only
    ;; gate ever removed from it. It ran generation through a LIVE OLLAMA and
    ;; proved `:imodelruntime-live-generate` -- which is to say it proved that
    ;; a third-party server generates tokens, and reported that as this
    ;; stack's maturity. The owner's direction is that no vLLM, Ollama, MLX or
    ;; llama.cpp sits underneath, so the gate went with its adapter.
    ;;
    ;; What it proved is NOT replaced, and saying otherwise would be the lie
    ;; this file exists to prevent: there is no live real-model generation
    ;; gate now. `:gemma4-e4b-native-parity` below still runs the native host
    ;; on the real GGUF and compares one token against a recorded oracle, and
    ;; that is a smaller claim than the one that left.
    :gemma4-e4b-native-parity
    :gemma4-metal-kdot
    :ollama-http-api
    ;; The Ollama surface's policy is Kotoba source; this gate is what keeps
    ;; the shipped KIR, the wire semantics, and native admission honest
    ;; (ADR-2608138800).
    :kotoba-decision-cores
    :kotoba-engine-kernel
    :ollama-chat-endpoint
    :openai-compatible-surface
    :session-memory-budget
    ;; The owner's direction has had no gate at all until now: inference with
    ;; no vLLM, Ollama, MLX or llama.cpp underneath, kotoba CLI and the amu
    ;; native binary only. Everything above measures either the portable CLJC
    ;; contract or the Ollama-compatible surface this repository SERVES, and
    ;; neither is the native path.
    :kotoba-native-executed})

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

(defn unblob
  "verify/maturity.edn is stored as Datomic/Datascript tx-data (a single-entity
  vector). Non-scalar values (nested maps, vectors-of-maps) are pr-str'd
  blobs; unwrap them back to live EDN. Public so other verify.* namespaces
  reading verify/maturity.edn (e.g. kotodama.verify.run-maturity) can reuse it."
  [v]
  (if (string? v)
    (try (let [parsed (edn/read-string v)] (if (coll? parsed) parsed v))
         (catch Exception _ v))
    v))

(defn reconstitute-entity [tx-data]
  (into {} (map (fn [[k v]] [(keyword (name k)) (unblob v)]))
        (dissoc (first tx-data) :db/id)))

(defn- read-maturity []
  (let [file (io/file "verify/maturity.edn")]
    (when-not (.isFile file)
      (fail! "missing maturity.edn" {:path (.getPath file)}))
    (reconstitute-entity (edn/read-string (slurp file)))))

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
    (when-not (contains? rt/supported-runtimes :torch-transformer)
      (fail! "runtime contract missing required foundation runtimes"
             {:supported-runtimes rt/supported-runtimes}))
    (doseq [runtime [:torch-transformer :torch-diffusion :torch-audio]]
      (when-not (contains? rt/supported-runtimes runtime)
        (fail! "missing supported runtime"
               {:runtime runtime
                :supported rt/supported-runtimes})))
    (doseq [task [:text-generation
                  :text-generation/mtp
                  :image-generation
                  :speech-to-text
                  :audio-transcription]]
      (when-not (contains? rt/supported-tasks task)
        (fail! "missing supported inference task"
               {:task task
                :supported rt/supported-tasks})))
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
