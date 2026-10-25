(ns lgx.llm
  "Shared OpenAI-compatible /chat/completions client for the lg-x graphs.

  Port note (ADR-2606280030 / ADR-2605215000): the Python graphs defaulted to a
  RunPod vLLM proxy (`https://…proxy.runpod.net/v1`). Per the inference invariant
  (Murakumo DEFAULT-PREFERRED, objective-function-assessed) this clj port defaults
  to the **Murakumo loopback LiteLLM gateway** (`http://127.0.0.1:4000/v1`) instead.
  The endpoint stays overridable via env (`MURAKUMO_URL` / legacy `VLLM_URL`) so a
  deployment can still point elsewhere; the wire shape is unchanged.

  httpx → babashka.http-client; json → cheshire."
  (:require [cheshire.core :as json]
            [kotoba.lang.text :as str]))

(def default-config {:base-url "http://127.0.0.1:4000/v1"
                     :model "tier0-general" :timeout-ms 60000})

(def ^:dynamic *http-post* nil)

(defn config [state]
  (merge default-config (or (get-in state [:host-config :llm]) {})))

(defn model [state] (:model (config state)))

(defn chat-completions
  "POST `{base}/chat/completions` with `payload` (a clj map). Returns a map:
    {:ok true  :resp <parsed-json> :latency-ms n}
    {:ok false :error <string>     :latency-ms n}
  Never throws — mirrors the Python try/except contract."
  [state payload]
  (when-not (fn? *http-post*)
    (throw (ex-info "X inference requires an explicit HTTP POST capability"
                    {:capability :x/llm-http-post})))
  (let [{:keys [base-url timeout-ms]} (config state)
        base-url (str/replace base-url #"/+$" "")
        started (System/nanoTime)
        latency #(int (/ (- (System/nanoTime) started) 1000000))]
    (try
      (let [r (*http-post* (str base-url "/chat/completions")
                         {:headers {"Content-Type" "application/json"}
                          :body (json/generate-string payload)
                          :timeout timeout-ms
                          :throw false})
            status (:status r)]
        (if (>= status 400)
          {:ok false
           :error (str "llm http " status ": " (subs (str (:body r)) 0 (min 200 (count (str (:body r))))))
           :latency-ms (latency)}
          {:ok true
           :resp (json/parse-string (:body r) true)
           :latency-ms (latency)}))
      (catch java.net.http.HttpTimeoutException _
        {:ok false :error (str "llm timeout after " (/ timeout-ms 1000) "s") :latency-ms (latency)})
      (catch Exception exc
        {:ok false
         :error (let [s (str "llm: " (.. exc getClass getSimpleName) ": " (.getMessage exc))]
                  (subs s 0 (min 200 (count s))))
         :latency-ms (latency)}))))
