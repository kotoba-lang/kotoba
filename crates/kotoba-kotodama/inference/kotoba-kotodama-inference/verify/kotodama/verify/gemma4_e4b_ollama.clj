(ns kotodama.verify.gemma4-e4b-ollama
  "Live local-model verification for the CLJC IModelRuntime boundary.

  This uses Ollama only as a local host adapter. The portable inference
  foundation remains torch-clj model graphs lowered to num-clj compute."
  (:require [clojure.string :as str]
            [kotodama.inference.core :as infer]
            [kotodama.inference.ollama :as ollama]
            [kotodama.inference.runtime :as rt])
  (:import [java.net URI]
           [java.net.http HttpClient HttpRequest HttpResponse$BodyHandlers]
           [java.time Duration]))

(def default-model "gemma4:e4b")
(def default-prompt "Say: kotoba.")
(def default-base-url "http://127.0.0.1:11434")
(def default-digest "c6eb396dbd5992bbe3f5cdb947e8bbc0ee413d7c17e2beaae69f5d569cf982eb")
(def default-parameter-size "8.0B")
(def default-quantization "Q4_K_M")

(defn- getenv [k default]
  (let [v (System/getenv k)]
    (if (str/blank? v) default v)))

(defn- parse-long-or [s default]
  (try
    (Long/parseLong (str s))
    (catch Exception _
      default)))

(defn- get-text [base-url path timeout-ms]
  (let [client (HttpClient/newHttpClient)
        request (-> (HttpRequest/newBuilder (URI/create (str base-url path)))
                    (.timeout (Duration/ofMillis timeout-ms))
                    (.GET)
                    (.build))
        response (.send client request (HttpResponse$BodyHandlers/ofString))
        status (.statusCode response)
        text (.body response)]
    (when-not (<= 200 status 299)
      (throw (ex-info "ollama tags request failed"
                      {:kotodama/status status
                       :kotodama/body text})))
    text))

(defn- require-contains! [text needle label]
  (when-not (str/includes? text needle)
    (throw (ex-info "gemma4:e4b model identity check failed"
                    {:kotodama/expected label
                     :kotodama/needle needle}))))

(defn- verify-model-identity! [{:keys [base-url model digest parameter-size quantization timeout-ms]}]
  (let [tags (get-text base-url "/api/tags" timeout-ms)]
    (require-contains! tags (str "\"name\":\"" model "\"") :model-name)
    (require-contains! tags (str "\"digest\":\"" digest "\"") :digest)
    (require-contains! tags "\"format\":\"gguf\"" :format)
    (require-contains! tags "\"family\":\"gemma4\"" :family)
    (require-contains! tags (str "\"parameter_size\":\"" parameter-size "\"") :parameter-size)
    (require-contains! tags (str "\"quantization_level\":\"" quantization "\"") :quantization)
    {:kotodama/model model
     :kotodama/digest digest
     :kotodama/format "gguf"
     :kotodama/family "gemma4"
     :kotodama/parameter-size parameter-size
     :kotodama/quantization quantization}))

(defn -main [& _]
  (let [model (getenv "KOTODAMA_VERIFY_MODEL" default-model)
        base-url (getenv "KOTODAMA_VERIFY_BASE_URL" default-base-url)
        digest (getenv "KOTODAMA_VERIFY_DIGEST" default-digest)
        parameter-size (getenv "KOTODAMA_VERIFY_PARAMETER_SIZE" default-parameter-size)
        quantization (getenv "KOTODAMA_VERIFY_QUANTIZATION" default-quantization)
        prompt (getenv "KOTODAMA_VERIFY_PROMPT" default-prompt)
        max-new-tokens (parse-long-or (getenv "KOTODAMA_VERIFY_MAX_NEW_TOKENS" "2") 2)
        timeout-ms (parse-long-or (getenv "KOTODAMA_VERIFY_TIMEOUT_MS" "600000") 600000)
        model-id (verify-model-identity! {:base-url base-url
                                          :model model
                                          :digest digest
                                          :parameter-size parameter-size
                                          :quantization quantization
                                          :timeout-ms timeout-ms})
        runtime (ollama/ollama-runtime {:base-url base-url
                                        :model model
                                        :timeout-ms timeout-ms})
        session (infer/load-model runtime
                                  (rt/transformer model
                                                  {:kotodama/backend :native
                                                   :kotodama/compute-backend :num/native}))
        result (infer/generate runtime session prompt
                               {:kotodama/max-new-tokens max-new-tokens
                                :kotodama/temperature 0})]
    (when (str/blank? (:kotodama/text result))
      (throw (ex-info "gemma4:e4b returned empty text"
                      {:kotodama/model model
                       :kotodama/result result})))
    (prn (merge model-id
                (select-keys result [:kotodama/runtime :kotodama/text])))))
