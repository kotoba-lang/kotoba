(ns kotodama.verify.qwen4exp-mtp-checkpoint
  "Verify the published Qwen3.8-Flash-Next MTP metadata without downloading
  model shards. This gate proves identity, exact tensor coverage, and the
  minimal shard acquisition set; it does not claim that the MTP decoder layer
  has executed."
  (:require [json.data-json :as json]
            [kotodama.inference.qwen4exp :as qwen4exp])
  (:import [java.net URI]
           [java.net.http HttpClient HttpRequest HttpResponse$BodyHandlers]
           [java.time Duration]))

(def ^:private revision "de4b8e4d43b917e7706784d8bb445c9af86a3540")

(def ^:private repository
  (str "https://huggingface.co/Qwen/Qwen3.8-Flash-Next/resolve/" revision "/"))

(defn- fetch-json [path]
  (let [client (-> (HttpClient/newBuilder)
                   (.followRedirects java.net.http.HttpClient$Redirect/NORMAL)
                   (.connectTimeout (Duration/ofSeconds 20))
                   .build)
        request (-> (HttpRequest/newBuilder (URI/create (str repository path)))
                    (.timeout (Duration/ofSeconds 60))
                    (.header "User-Agent" "kotodama-qwen4exp-mtp-verifier/1")
                    .GET
                    .build)
        response (.send client request (HttpResponse$BodyHandlers/ofString))]
    (when-not (= 200 (.statusCode response))
      (throw (ex-info "official checkpoint metadata fetch failed"
                      {:path path :status (.statusCode response)})))
    (json/read-str (.body response))))

(defn -main [& _]
  (let [config (fetch-json "config.json")
        index (fetch-json "model.safetensors.index.json")
        audit (qwen4exp/checkpoint-audit config index)
        expected-tensors (count (qwen4exp/required-mtp-tensors 1))]
    (when-not (and (:kotodama/mtp-admitted? audit)
                   (= 1 (:kotodama/mtp-layer-count audit))
                   (= expected-tensors (:kotodama/mtp-tensor-count audit))
                   (= 28 (count (:kotodama/mtp-shards audit))))
      (throw (ex-info "published checkpoint is not the expected MTP artifact"
                      (assoc audit :kotodama/expected-mtp-tensors expected-tensors))))
    (prn (assoc audit
                :kotodama/model "Qwen/Qwen3.8-Flash-Next"
                :kotodama/revision revision
                :kotodama/metadata-source :huggingface/official
                :kotodama/mtp-checkpoint :verified
                :kotodama/mtp-decoder-executed? false))))
