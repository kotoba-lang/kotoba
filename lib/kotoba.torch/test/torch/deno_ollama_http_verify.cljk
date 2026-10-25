(ns torch.deno-ollama-http-verify
  (:require [torch.ollama :as ollama]
            [torch.ollama-http :as http]
            [torch.model-registry :as registry]
            [torch.registry-runtime :as registry-runtime]))

(defn- body-json [response]
  (.json response))

(defn -main [& _]
  (let [created "2026-07-14T00:00:00Z"
        chunks [(ollama/token-chunk "tiny" created "hel")
                (ollama/token-chunk "tiny" created "lo")
                (ollama/done-chunk "tiny" created [1 2 3]
                                   {:eval-count 2 :done-reason "stop"})]
        stream-source
        (fn []
          (let [timers (atom [])]
            (js/ReadableStream.
             #js {:start (fn [controller]
                           (.enqueue controller (first chunks))
                           (reset! timers
                                   [(js/setTimeout
                                     #(.enqueue controller (second chunks)) 60)
                                    (js/setTimeout
                                     #(do (.enqueue controller (last chunks))
                                          (.close controller)) 120)]))
                  :cancel (fn [_]
                            (doseq [timer @timers] (js/clearTimeout timer)))})))
        live-cancellations (atom [])
        lifecycle-calls (atom [])
        model-events (atom [])
        model-runtime
        (registry-runtime/runtime
         (-> (registry/registry
              2048
              (fn [descriptor]
                (swap! model-events conj [:load (:name descriptor)])
                {:name (:name descriptor)})
              (fn [resource]
                (swap! model-events conj [:unload (:name resource)])))
             (registry/register
              {:name "tiny:latest" :size 1234 :digest "sha256:test"})))
        _ (registry-runtime/acquire! model-runtime "tiny:latest" 0)
        service {:version "0.12.0"
                 :models #(registry-runtime/tags model-runtime)
                 :running-models #(registry-runtime/running-models model-runtime)
                 :show-model (fn [name _]
                               {:details {:family "llama"} :model_info {:name name}})
                 :copy-model! (fn [source destination]
                                (swap! lifecycle-calls conj
                                       [:copy source destination]))
                 :delete-model! (fn [model]
                                  (swap! lifecycle-calls conj [:delete model]))
                 :embed! (fn [request _]
                           (js/Promise.resolve
                            {:embeddings (mapv (fn [_] [0.6 0.8]) (:inputs request))
                             :prompt-eval-count (count (:inputs request))}))
                 :generate! (fn [_ _] (js/Promise.resolve chunks))
                 :generate-stream! (fn [_ _]
                                     (js/Promise.resolve (stream-source)))
                 :cancel! (fn [request-id reason]
                            (swap! live-cancellations conj [request-id reason]))}
        handler (http/handler service)
        server (http/serve! service {:hostname "127.0.0.1" :port 0})
        base-url (str "http://127.0.0.1:" (.-port (.-addr server)))
        live-url (str base-url "/api/version")
        first-byte-start (.now js/performance)
        live-first-byte
        (-> (js/fetch
             (str base-url "/api/generate")
             #js {:method "POST"
                  :headers #js {"content-type" "application/json"}
                  :body (js/JSON.stringify
                         #js {:model "tiny" :prompt "hi" :stream true})})
            (.then
             (fn [response]
               (let [reader (.getReader (.-body response))]
                 (-> (.read reader)
                     (.then (fn [result]
                              (.cancel reader)
                              #js {:status (.-status response)
                                   :elapsed (- (.now js/performance)
                                               first-byte-start)
                                   :bytes (.-byteLength (.-value result))})))))))
        openai-first-byte-start (.now js/performance)
        openai-live-first-byte
        (-> (js/fetch
             (str base-url "/v1/chat/completions")
             #js {:method "POST"
                  :headers #js {"content-type" "application/json"}
                  :body (js/JSON.stringify
                         #js {:model "tiny" :stream true
                              :messages #js [#js {:role "user" :content "hi"}]})})
            (.then
             (fn [response]
               (let [reader (.getReader (.-body response))]
                 (-> (.read reader)
                     (.then
                      (fn [result]
                        (let [measurement
                              #js {:status (.-status response)
                                   :content-type
                                   (.get (.-headers response) "content-type")
                                   :elapsed (- (.now js/performance)
                                               openai-first-byte-start)
                                   :bytes (.-byteLength (.-value result))}]
                          (.then (.cancel reader)
                                 (fn [_] measurement))))))))))
        cancellations (atom [])
        abort-controller (js/AbortController.)
        abort-handler
        (http/handler
         {:request-id-fn (constantly "abort-me")
          :cancel! (fn [request-id reason]
                     (swap! cancellations conj [request-id reason]))
          :generate! (fn [_ _]
                       (js/Promise. (fn [resolve _]
                                      (js/setTimeout #(resolve chunks) 10))))})
        version-request (js/Request. "http://localhost/api/version")
        tags-request (js/Request. "http://localhost/api/tags")
        ps-request (js/Request. "http://localhost/api/ps")
        show-request (js/Request. "http://localhost/api/show"
                                  #js {:method "POST"
                                       :headers #js {"content-type" "application/json"}
                                       :body (js/JSON.stringify #js {:model "tiny:latest"})})
        stream-request
        (js/Request. "http://localhost/api/generate"
                     #js {:method "POST"
                          :headers #js {"content-type" "application/json"}
                          :body (js/JSON.stringify
                                 #js {:model "tiny" :prompt "hi" :stream true})})
        one-request
        (js/Request. "http://localhost/api/generate"
                     #js {:method "POST"
                          :headers #js {"content-type" "application/json"}
                          :body (js/JSON.stringify
                                 #js {:model "tiny" :prompt "hi" :stream false})})
        bad-request
        (js/Request. "http://localhost/api/generate"
                     #js {:method "POST"
                          :headers #js {"content-type" "application/json"}
                          :body (js/JSON.stringify #js {:model "" :prompt 1})})
        chat-stream-request
        (js/Request. "http://localhost/api/chat"
                     #js {:method "POST"
                          :headers #js {"content-type" "application/json"}
                          :body (js/JSON.stringify
                                 #js {:model "tiny" :stream true
                                      :messages #js [#js {:role "user"
                                                          :content "hi"}]})})
        chat-one-request
        (js/Request. "http://localhost/api/chat"
                     #js {:method "POST"
                          :headers #js {"content-type" "application/json"}
                          :body (js/JSON.stringify
                                 #js {:model "tiny" :stream false
                                      :messages #js [#js {:role "user"
                                                          :content "hi"}]})})
        embed-request
        (js/Request. "http://localhost/api/embed"
                     #js {:method "POST"
                          :headers #js {"content-type" "application/json"}
                          :body (js/JSON.stringify
                                 #js {:model "tiny"
                                      :input #js ["one" "two"]})})
        copy-request
        (js/Request. "http://localhost/api/copy"
                     #js {:method "POST"
                          :headers #js {"content-type" "application/json"}
                          :body (js/JSON.stringify
                                 #js {:source "tiny:latest"
                                      :destination "tiny:backup"})})
        delete-request
        (js/Request. "http://localhost/api/delete"
                     #js {:method "DELETE"
                          :headers #js {"content-type" "application/json"}
                          :body (js/JSON.stringify #js {:model "tiny:backup"})})
        openai-models-request (js/Request. "http://localhost/v1/models")
        openai-model-request
        (js/Request. "http://localhost/v1/models/tiny%3Alatest")
        openai-missing-model-request
        (js/Request. "http://localhost/v1/models/missing")
        openai-chat-stream-request
        (js/Request. "http://localhost/v1/chat/completions"
                     #js {:method "POST"
                          :headers #js {"content-type" "application/json"}
                          :body (js/JSON.stringify
                                 #js {:model "tiny" :stream true
                                      :messages #js [#js {:role "user"
                                                          :content "hi"}]})})
        openai-chat-one-request
        (js/Request. "http://localhost/v1/chat/completions"
                     #js {:method "POST"
                          :headers #js {"content-type" "application/json"}
                          :body (js/JSON.stringify
                                 #js {:model "tiny"
                                      :messages #js [#js {:role "user"
                                                          :content "hi"}]})})
        openai-embed-request
        (js/Request. "http://localhost/v1/embeddings"
                     #js {:method "POST"
                          :headers #js {"content-type" "application/json"}
                          :body (js/JSON.stringify
                                 #js {:model "tiny" :input #js ["one" "two"]})})
        openai-bad-request
        (js/Request. "http://localhost/v1/chat/completions"
                     #js {:method "POST"
                          :headers #js {"content-type" "application/json"}
                          :body (js/JSON.stringify
                                 #js {:model "tiny" :n 2
                                      :messages #js [#js {:role "user"
                                                          :content "hi"}]})})
        abort-request
        (js/Request. "http://localhost/api/generate"
                     #js {:method "POST"
                          :signal (.-signal abort-controller)
                          :headers #js {"content-type" "application/json"}
                          :body (js/JSON.stringify
                                 #js {:model "tiny" :prompt "hi"})})
        aborted-response (abort-handler abort-request)
        _ (.abort abort-controller)]
    (-> (js/Promise.all
         #js [(handler version-request) (handler tags-request)
              (handler ps-request) (handler show-request)
              (handler stream-request) (handler one-request)
              (handler bad-request) (js/fetch live-url) aborted-response
              (handler chat-stream-request) (handler chat-one-request)
              (handler embed-request)
              live-first-byte (handler copy-request) (handler delete-request)
              (handler openai-models-request) (handler openai-model-request)
              (handler openai-missing-model-request)
              (handler openai-chat-stream-request)
              (handler openai-chat-one-request) (handler openai-embed-request)
              (handler openai-bad-request) openai-live-first-byte])
        (.then
         (fn [responses]
           (let [version (aget responses 0)
                 tags (aget responses 1)
                 ps (aget responses 2)
                 show (aget responses 3)
                 stream (aget responses 4)
                 one (aget responses 5)
                 bad (aget responses 6)
                 live (aget responses 7)
                 chat-stream (aget responses 9)
                 chat-one (aget responses 10)
                 embed (aget responses 11)
                 first-byte (aget responses 12)
                 copy-response (aget responses 13)
                 delete-response (aget responses 14)
                 openai-models (aget responses 15)
                 openai-model (aget responses 16)
                 openai-missing-model (aget responses 17)
                 openai-chat-stream (aget responses 18)
                 openai-chat-one (aget responses 19)
                 openai-embed (aget responses 20)
                 openai-bad (aget responses 21)
                 openai-first-byte (aget responses 22)]
             (-> (js/Promise.all
                  #js [(body-json version) (body-json tags) (body-json ps)
                       (body-json show) (.text stream)
                       (body-json one) (body-json bad)
                       (.text chat-stream) (body-json chat-one)
                       (body-json embed) (body-json copy-response)
                       (body-json delete-response)
                       (body-json openai-models) (body-json openai-model)
                       (body-json openai-missing-model) (.text openai-chat-stream)
                       (body-json openai-chat-one) (body-json openai-embed)
                       (body-json openai-bad)])
                 (.then
                  (fn [bodies]
                    (let [version-body (aget bodies 0)
                          tags-body (aget bodies 1)
                          ps-body (aget bodies 2)
                          show-body (aget bodies 3)
                          stream-lines (-> (aget bodies 4) .trim (.split "\n"))
                          one-body (aget bodies 5)
                          bad-body (aget bodies 6)
                          chat-lines (-> (aget bodies 7) .trim (.split "\n"))
                          chat-one-body (aget bodies 8)
                          embed-body (aget bodies 9)
                          openai-models-body (aget bodies 12)
                          openai-model-body (aget bodies 13)
                          openai-missing-model-body (aget bodies 14)
                          openai-stream-events (->> (.split (aget bodies 15) "\n\n")
                                                    (remove empty?) vec)
                          openai-chat-one-body (aget bodies 16)
                          openai-embed-body (aget bodies 17)
                          openai-bad-body (aget bodies 18)
                          _ (registry-runtime/release!
                             model-runtime "tiny:latest" 1 0)
                          _ (registry-runtime/expire! model-runtime 1)
                          ok? (and (= 200 (.-status version))
                                   (= "0.12.0" (.-version version-body))
                                   (= 1 (.-length (.-models tags-body)))
                                   (= 1 (.-length (.-models ps-body)))
                                   (= "llama" (.. show-body -details -family))
                                   (= "application/x-ndjson"
                                      (.get (.-headers stream) "content-type"))
                                   (= 3 (.-length stream-lines))
                                   (= "hello" (.-response one-body))
                                   (true? (.-done one-body))
                                   (= 400 (.-status bad))
                                   (string? (.-error bad-body))
                                   (= 3 (.-length chat-lines))
                                   (= "hello" (.. chat-one-body -message -content))
                                   (true? (.-done chat-one-body))
                                   (= 2 (.-length (.-embeddings embed-body)))
                                   (= 2 (.-prompt_eval_count embed-body))
                                   (= 200 (.-status copy-response))
                                   (= 200 (.-status delete-response))
                                   (= #{[:copy "tiny:latest" "tiny:backup"]
                                        [:delete "tiny:backup"]}
                                      (set @lifecycle-calls))
                                   (= "list" (.-object openai-models-body))
                                   (= "tiny:latest" (.-id openai-model-body))
                                   (= 404 (.-status openai-missing-model))
                                   (string? (.. openai-missing-model-body -error -message))
                                   (= "text/event-stream"
                                      (.get (.-headers openai-chat-stream)
                                            "content-type"))
                                   (= 4 (count openai-stream-events))
                                   (= "data: [DONE]" (last openai-stream-events))
                                   (= "hello" (.. openai-chat-one-body -choices
                                                  (at 0) -message -content))
                                   (= 2 (.. openai-chat-one-body -usage -total_tokens))
                                   (= 2 (.-length (.-data openai-embed-body)))
                                   (= 400 (.-status openai-bad))
                                   (string? (.. openai-bad-body -error -message))
                                   (= 200 (.-status openai-first-byte))
                                   (= "text/event-stream"
                                      (aget openai-first-byte "content-type"))
                                   (< (.-elapsed openai-first-byte) 100)
                                   (pos? (.-bytes openai-first-byte))
                                   (= 200 (.-status live))
                                   (= 200 (.-status first-byte))
                                   (< (.-elapsed first-byte) 100)
                                   (pos? (.-bytes first-byte))
                                   (= 2 (count @live-cancellations))
                                   (= [[:load "tiny:latest"]
                                       [:unload "tiny:latest"]]
                                      @model-events)
                                   (= [["abort-me" :client-disconnect]]
                                      @cancellations))]
                      (println "Ollama version/tags/ps/show endpoints:"
                               (if (and (= 200 (.-status version))
                                        (= 200 (.-status tags))
                                        (= 200 (.-status ps))
                                        (= 200 (.-status show))) "passed" "failed"))
                      (println "Ollama stream/non-stream generate:"
                               (if ok? "passed" "failed"))
                      (println "Ollama stream/non-stream chat:"
                               (if (and (= 3 (.-length chat-lines))
                                        (= "hello" (.. chat-one-body -message -content)))
                                 "passed" "failed"))
                      (println "Ollama batched embed endpoint:"
                               (if (= 2 (.-length (.-embeddings embed-body)))
                                 "passed" "failed"))
                      (println "Ollama copy/delete model endpoints:"
                               (if (and (= 200 (.-status copy-response))
                                        (= 200 (.-status delete-response))
                                        (= 2 (count @lifecycle-calls)))
                                 "passed" "failed"))
                      (println "OpenAI models/chat/embeddings compatibility:"
                               (if (and (= 4 (count openai-stream-events))
                                        (= "hello" (.. openai-chat-one-body
                                                       -choices (at 0)
                                                       -message -content))
                                        (= 2 (.-length (.-data openai-embed-body)))
                                        (< (.-elapsed openai-first-byte) 100))
                                 "passed" "failed"))
                      (println "Ollama invalid request status:"
                               (if (= 400 (.-status bad)) "passed" "failed"))
                      (println "Deno TCP listener and client abort:"
                               (if (and (= 200 (.-status live))
                                        (= 1 (count @cancellations)))
                                 "passed" "failed"))
                      (println "incremental first NDJSON byte before completion:"
                               (if (and (< (.-elapsed first-byte) 100)
                                        (pos? (.-bytes first-byte))
                                        (= 2 (count @live-cancellations)))
                                 "passed" "failed"))
                      (.shutdown server)
                      (when-not ok? (.exit js/Deno 1)))))))))
        (.catch (fn [error] (js/console.error error) (.exit js/Deno 1))))))

(set! *main-cli-fn* -main)
