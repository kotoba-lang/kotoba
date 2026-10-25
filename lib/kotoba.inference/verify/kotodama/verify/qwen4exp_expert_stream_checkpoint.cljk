(ns kotodama.verify.qwen4exp-expert-stream-checkpoint
  "Verify the exact official routed-expert index without downloading weights."
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
                   (.connectTimeout (Duration/ofSeconds 20)) .build)
        request (-> (HttpRequest/newBuilder (URI/create (str repository path)))
                    (.timeout (Duration/ofSeconds 60))
                    (.header "User-Agent" "kotodama-qwen4exp-expert-stream-verifier/1")
                    .GET .build)
        response (.send client request (HttpResponse$BodyHandlers/ofString))]
    (when-not (= 200 (.statusCode response))
      (throw (ex-info "official checkpoint metadata fetch failed"
                      {:path path :status (.statusCode response)})))
    (json/read-str (.body response))))

(defn -main [& _]
  (let [audit (qwen4exp/expert-stream-audit
               (fetch-json "config.json")
               (fetch-json "model.safetensors.index.json"))]
    (when-not (and (:kotodama/expert-stream-admitted? audit)
                   (= 48 (:kotodama/layers audit))
                   (= 512 (:kotodama/experts audit))
                   (= 10 (:kotodama/active-experts audit))
                   (= 96 (:kotodama/expert-tensor-count audit))
                   (= 387 (:kotodama/hyper-connection-tensor-count audit))
                   (empty? (:kotodama/hyper-connection-missing audit))
                   (= 9830400 (:kotodama/bf16-bytes-per-expert audit)))
      (throw (ex-info "published checkpoint is not the expected expert layout" audit)))
    (prn (assoc audit
                :kotodama/model "Qwen/Qwen3.8-Flash-Next"
                :kotodama/revision revision
                :kotodama/metadata-source :huggingface/official
                :kotodama/expert-stream-checkpoint :verified
                :kotodama/real-generation? false))))
