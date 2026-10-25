(ns torch.deno-public-gguf-ollama-verify
  "Serve the real public GGUF Metal model through an actual Ollama HTTP socket."
  (:require [num.deno-gpu :as gpu]
            [torch.deno-public-gguf-metal-verify :as metal]
            [torch.generate :as generate]
            [torch.metal-bundle :as bundle]
            [torch.num-backend :as nb]
            [torch.ollama :as ollama]
            [torch.ollama-http :as http]
            [torch.tokenizer :as tokenizer]))

(def created-at "2026-07-14T00:00:00Z")

(defn- run-request
  [{:keys [backend model weights tokenizer active cancelled]} request context emit!]
  (let [request-id (:request-id context)
        prompt-ids (tokenizer/encode tokenizer (:prompt request))
        max-tokens (min 24 (get-in request [:sampling :max-new-tokens]))
        sampling (assoc (:sampling request) :temperature
                        (get-in request [:sampling :temperature]))
        caches* (atom (nb/init-llama-caches backend model 32))
        started (.now js/performance)
        pending
        (-> (metal/prefill backend model weights @caches* prompt-ids)
            (.then
             (fn [prefilled]
               (reset! caches* (:caches prefilled))
               (letfn [(advance [logits generated decode-state]
                         (if (contains? @cancelled request-id)
                           (js/Promise.resolve {:cancelled? true :generated generated})
                           (let [token-id (generate/sample-token
                                           logits
                                           (assoc sampling :previous-tokens
                                                  (into prompt-ids generated)))
                                 decoded (tokenizer/decode-step
                                          tokenizer decode-state token-id)
                                 generated* (conj generated token-id)]
                             (emit! (ollama/token-chunk
                                     (:model request) created-at (:text decoded)))
                             (if (or (= token-id (:eos-id tokenizer))
                                     (>= (count generated*) max-tokens))
                               (let [elapsed (* 1.0e6 (- (.now js/performance) started))]
                                 (emit! (ollama/done-chunk
                                         (:model request) created-at
                                         (into prompt-ids generated*)
                                         {:prompt-eval-count (count prompt-ids)
                                          :eval-count (count generated*)
                                          :total-duration elapsed
                                          :eval-duration elapsed}))
                                 (js/Promise.resolve
                                  {:generated generated* :cancelled? false}))
                               (-> (metal/step-read backend model weights token-id @caches*)
                                   (.then (fn [step]
                                            (reset! caches* (:caches step))
                                            (advance (:logits step) generated*
                                                     (:state decoded)))))))))]
                 (advance (:logits prefilled) [] nil))))
            (.finally (fn [] (nb/release-llama-caches! @caches*))))]
    (swap! active conj pending)
    pending))

(defn- stream-source [environment request context]
  (let [controller* (atom nil)]
    (js/ReadableStream.
     #js {:start
          (fn [controller]
            (reset! controller* controller)
            (-> (run-request environment request context #(.enqueue controller %))
                (.then (fn [_] (.close controller)))
                (.catch (fn [error]
                          (when-not (contains? @(:cancelled environment)
                                               (:request-id context))
                            (.error controller error))))))
          :cancel (fn [_]
                    (swap! (:cancelled environment) conj (:request-id context)))})))

(defn- collect-request [environment request context]
  (let [chunks (atom [])]
    (-> (run-request environment request context #(swap! chunks conj %))
        (.then (fn [_] @chunks)))))

(defn- read-ndjson-stream [response started]
  (let [reader (.getReader (.-body response))
        decoder (js/TextDecoder.)]
    (letfn [(pump [parts first-byte-ms]
              (-> (.read reader)
                  (.then
                   (fn [result]
                     (if (.-done result)
                       (let [body (apply str parts)]
                         {:first-byte-ms first-byte-ms
                          :chunks
                          (mapv #(js->clj (js/JSON.parse %)
                                          :keywordize-keys true)
                                (.split (.trim body) "\n"))})
                       (pump (conj parts (.decode decoder (.-value result)
                                                   #js {:stream true}))
                             (or first-byte-ms
                                 (- (.now js/performance) started))))))))]
      (pump [] nil))))

(defn -main [& [bundle-path]]
  (let [bundle (bundle/load-bundle bundle-path)]
    (-> (gpu/request-device)
        (.then
         (fn [request]
           (let [backend (gpu/backend request)
                 baseline (gpu/backend-stats backend)
                 environment {:backend backend
                              :model (metal/build-model (:config bundle))
                              :weights (metal/upload-weights backend (:weights bundle))
                              :tokenizer (tokenizer/tokenizer (:tokenizer bundle))
                              :active (atom []) :cancelled (atom #{})}
                 request-counter (atom 0)
                 cancellations (atom [])
                 service {:version "0.12.0-metal"
                          :models [{:name "tiny-random-llama:latest"
                                    :size (.-size (js/Deno.statSync bundle-path))}]
                          :request-id-fn #(str "real-" (swap! request-counter inc))
                          :generate-stream! #(js/Promise.resolve
                                              (stream-source environment %1 %2))
                          :generate! #(collect-request environment %1 %2)
                          :cancel! (fn [id reason]
                                     (swap! cancellations conj [id reason])
                                     (swap! (:cancelled environment) conj id))}
                 server (http/serve! service {:hostname "127.0.0.1" :port 0})
                 base (str "http://127.0.0.1:" (.-port (.-addr server)))
                 body (fn [stream n]
                        (js/JSON.stringify
                         (clj->js {:model "tiny-random-llama:latest"
                                   :prompt "Hello" :stream stream
                                   :options {:temperature 0.0 :num_predict n}})))
                 post (fn [payload signal]
                        (js/fetch (str base "/api/generate")
                                  (clj->js (cond-> {:method "POST"
                                                   :headers {"content-type"
                                                             "application/json"}
                                                   :body payload}
                                            signal (assoc :signal signal)))))
                 stream-start (.now js/performance)]
             (println "Real GGUF Ollama HTTP on" (gpu/adapter-description request))
             (-> (post (body true 4) nil)
                 (.then
                  (fn [response]
                    (-> (read-ndjson-stream response stream-start)
                        (.then (fn [{:keys [chunks first-byte-ms]}]
                                 {:chunks chunks :first-ms first-byte-ms
                                  :stream-ms (- (.now js/performance)
                                                stream-start)})))))
                 (.then
                  (fn [stream-result]
                    (-> (post (body false 4) nil)
                        (.then #(.json %))
                        (.then (fn [nonstream]
                                 (assoc stream-result :nonstream nonstream))))))
                 (.then
                  (fn [results]
                    (let [aborter (js/AbortController.)]
                      (-> (post (body true 20) (.-signal aborter))
                          (.then
                           (fn [response]
                             (let [reader (.getReader (.-body response))]
                               (-> (.read reader)
                                   (.then (fn [_]
                                            (.abort aborter)
                                            results))))))))))
                 (.then
                  (fn [results]
                    (-> (js/Promise.all (into-array @(:active environment)))
                        (.catch (fn [_] nil))
                        (.then (fn [_] results)))))
                 (.then
                  (fn [{:keys [chunks nonstream first-ms stream-ms]}]
                    (let [stream-context (:context (last chunks))
                          expected (into (:prompt-ids bundle)
                                         (:generated-ids bundle))
                          nonstream-context (vec (js->clj (.-context nonstream)))
                          ok? (and (= expected stream-context nonstream-context)
                                   (true? (:done (last chunks)))
                                   (true? (.-done nonstream))
                                   (< first-ms stream-ms)
                                   (seq @cancellations))]
                      (println "real streamed context parity:"
                               (if (= expected stream-context) "passed" "failed"))
                      (println "real non-stream context parity:"
                               (if (= expected nonstream-context) "passed" "failed"))
                      (println "first response ms:" (.toFixed first-ms 3))
                      (println "complete stream ms:" (.toFixed stream-ms 3))
                      (println "incremental first byte before completion:"
                               (if (< first-ms stream-ms) "passed" "failed"))
                      (println "client disconnect cancellation:"
                               (if (seq @cancellations) "passed" "failed"))
                      (.shutdown server)
                      (nb/release-weights! (:weights environment))
                      (let [after (gpu/backend-stats backend)
                            restored?
                            (and (= (:live-buffers baseline) (:live-buffers after))
                                 (= (:live-bytes baseline) (:live-bytes after))
                                 (= (- (:created-buffers after)
                                       (:created-buffers baseline))
                                    (- (:destroyed-buffers after)
                                       (:destroyed-buffers baseline)))
                                 (= (- (:created-bytes after) (:created-bytes baseline))
                                    (- (:destroyed-bytes after)
                                       (:destroyed-bytes baseline))))]
                        (println "GPU baseline restored:"
                                 (if restored? "passed" "failed"))
                        (when-not (and ok? restored?)
                          (throw (js/Error. "real Ollama Metal verification failed")))))))))))
        (.then #(js/Deno.exit 0))
        (.catch (fn [error]
                  (println "ERROR:" (or (.-stack error) (str error)))
                  (js/Deno.exit 1))))))

(set! *main-cli-fn* -main)
