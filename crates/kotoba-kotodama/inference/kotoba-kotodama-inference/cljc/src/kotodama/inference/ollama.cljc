(ns kotodama.inference.ollama
  "CLJC host adapter for a local Ollama model runtime.

  This is intentionally a host implementation of `kotodama.inference.ports/
  IModelRuntime`, not the portable model contract itself. The contract remains
  torch-clj model graph + num-clj compute backend; Ollama is a practical local
  real-model host used to prove natural-language generation end to end."
  (:require [kotodama.inference.ports :as ports])
  #?(:clj
     (:import [java.net URI]
              [java.net.http HttpClient HttpRequest HttpRequest$BodyPublishers
               HttpResponse$BodyHandlers]
              [java.time Duration])))

(def default-base-url "http://127.0.0.1:11434")

(defn- json-escape [s]
  (-> (str s)
      (.replace "\\" "\\\\")
      (.replace "\"" "\\\"")
      (.replace "\n" "\\n")
      (.replace "\r" "\\r")
      (.replace "\t" "\\t")))

(defn- json-body [m]
  (str "{"
       (->> m
            (keep (fn [[k v]]
                    (when (some? v)
                      (str "\"" (name k) "\":"
                           (cond
                             (string? v) (str "\"" (json-escape v) "\"")
                             (keyword? v) (str "\"" (name v) "\"")
                             (number? v) (str v)
                             (boolean? v) (str v)
                             (map? v) (json-body v)
                             :else (str "\"" (json-escape v) "\""))))))
            (interpose ",")
            (apply str))
       "}"))

(defn- unescape-json-string [s]
  (loop [xs (seq s), out (StringBuilder.)]
    (if-not xs
      (str out)
      (let [c (first xs)]
        (if (not= c \\)
          (do (.append out c) (recur (next xs) out))
          (let [e (second xs)
                more (nnext xs)]
            (case e
              \" (do (.append out \") (recur more out))
              \\ (do (.append out \\) (recur more out))
              \/ (do (.append out \/) (recur more out))
              \b (do (.append out \backspace) (recur more out))
              \f (do (.append out \formfeed) (recur more out))
              \n (do (.append out \newline) (recur more out))
              \r (do (.append out \return) (recur more out))
              \t (do (.append out \tab) (recur more out))
              (do (.append out e) (recur more out)))))))))

(defn- extract-json-string [json field]
  (let [needle (str "\"" field "\":\"")
        start (.indexOf ^String json needle)]
    (when (not= -1 start)
      (let [from (+ start (count needle))]
        (loop [i from, escaped? false]
          (when (< i (count json))
            (let [c (.charAt ^String json i)]
              (cond
                escaped? (recur (inc i) false)
                (= c \\) (recur (inc i) true)
                (= c \") (unescape-json-string (subs json from i))
                :else (recur (inc i) false)))))))))

#?(:clj
   (defn- post-json [base-url path body timeout-ms]
     (let [client (HttpClient/newHttpClient)
           request (-> (HttpRequest/newBuilder (URI/create (str base-url path)))
                       (.timeout (Duration/ofMillis timeout-ms))
                       (.header "content-type" "application/json")
                       (.POST (HttpRequest$BodyPublishers/ofString body))
                       (.build))
           response (.send client request (HttpResponse$BodyHandlers/ofString))
           status (.statusCode response)
           text (.body response)]
       (if (<= 200 status 299)
         text
         (throw (ex-info "ollama request failed"
                         {:kotodama/status status
                          :kotodama/body text}))))))

(defn ollama-runtime
  "Create a CLJ-side `IModelRuntime` backed by Ollama's local HTTP API.

  Options:
  - `:base-url` defaults to `http://127.0.0.1:11434`
  - `:model` defaults to the model in the runtime spec/session
  - `:timeout-ms` defaults to 180000"
  ([] (ollama-runtime {}))
  ([{:keys [base-url model timeout-ms]
     :or {base-url default-base-url timeout-ms 180000}}]
   #?(:clj
      (ports/fn-runtime
        {:probe (fn [] {:kotodama/backends [:ollama]
                        :kotodama/base-url base-url})
         :load (fn [runtime-spec]
                 {:kotodama/session-id (str "ollama:" (or model (:kotodama/model runtime-spec)))
                  :kotodama/runtime :ollama
                  :kotodama/model (or model (:kotodama/model runtime-spec))
                  :kotodama/spec runtime-spec})
         :generate (fn [session prompt generation]
                     (let [model-id (or model (:kotodama/model session))
                           response (post-json
                                      base-url
                                      "/api/generate"
                                      (json-body {:model model-id
                                                  :prompt prompt
                                                  :stream false
                                                  :options {:num_predict
                                                            (:kotodama/max-new-tokens generation 64)
                                                            :temperature
                                                            (:kotodama/temperature generation 0.2)}})
                                      timeout-ms)
                           text (or (extract-json-string response "response") "")]
                       {:kotodama/text text
                        :kotodama/model model-id
                        :kotodama/runtime :ollama
                        :kotodama/raw response}))
         :forward (fn [_ _ _]
                    (throw (ex-info "ollama runtime does not expose raw tensor forward"
                                    {:kotodama/runtime :ollama})))})
      :cljs
      (throw (js/Error. "ollama-runtime is a host adapter; provide a CLJS fetch-backed IModelRuntime instead")))))
