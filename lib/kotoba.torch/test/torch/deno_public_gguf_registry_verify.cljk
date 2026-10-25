(ns torch.deno-public-gguf-registry-verify
  "Lazy real-model residency, name routing, LRU eviction, and tags on Metal."
  (:require [num.deno-gpu :as gpu]
            [torch.deno-public-gguf-continuous-verify :as fixture]
            [torch.metal-bundle :as bundle]
            [torch.metal-resource :as resource]
            [torch.model-registry :as registry]
            [torch.ollama-http :as http]
            [torch.registry-ollama :as registry-ollama]
            [torch.registry-runtime :as registry-runtime]))

(defn- post [url model keep-alive]
  (-> (js/fetch
       url
       #js {:method "POST" :headers #js {"content-type" "application/json"}
            :body (js/JSON.stringify
                   (clj->js {:model model :prompt "Hello" :stream false
                             :keep_alive keep-alive
                             :options {:temperature 0.0 :num_predict 2}}))})
      (.then #(.json %))))

(defn- json-get [url]
  (-> (js/fetch url) (.then #(.json %))))

(defn- show [url model]
  (-> (js/fetch url #js {:method "POST"
                          :headers #js {"content-type" "application/json"}
                          :body (js/JSON.stringify (clj->js {:model model}))})
      (.then (fn [response]
               (-> (.json response)
                   (.then #(vector (.-status response) %)))))))

(defn- mutate-model [url method body]
  (-> (js/fetch url #js {:method method
                          :headers #js {"content-type" "application/json"}
                          :body (js/JSON.stringify (clj->js body))})
      (.then (fn [response]
               (-> (.json response)
                   (.then #(vector (.-status response) %)))))))

(defn- chat [url model]
  (-> (js/fetch
       url #js {:method "POST" :headers #js {"content-type" "application/json"}
                :body (js/JSON.stringify
                       (clj->js {:model model :stream false :keep_alive -1
                                 :messages [{:role "system" :content "Be brief"}
                                            {:role "user" :content "Hello"}]
                                 :options {:temperature 0.0 :num_predict 2}}))})
      (.then #(.json %))))

(defn- embed [url model]
  (-> (js/fetch
       url #js {:method "POST" :headers #js {"content-type" "application/json"}
                :body (js/JSON.stringify
                       (clj->js {:model model :input ["Hi" "Hello"]
                                 :keep_alive -1}))})
      (.then #(.json %))))

(defn- openai-chat [url model]
  (-> (js/fetch
       url #js {:method "POST" :headers #js {"content-type" "application/json"}
                :body (js/JSON.stringify
                       (clj->js {:model model :stream false :max_tokens 2
                                 :messages [{:role "user" :content "Hello"}]}))})
      (.then #(.json %))))

(defn- openai-embed [url model]
  (-> (js/fetch
       url #js {:method "POST" :headers #js {"content-type" "application/json"}
                :body (js/JSON.stringify
                       (clj->js {:model model :input ["Hi" "Hello"]}))})
      (.then #(.json %))))

(defn- invalid-embed [url model]
  (-> (js/fetch
       url #js {:method "POST" :headers #js {"content-type" "application/json"}
                :body (js/JSON.stringify
                       (clj->js {:model model :input "Hi" :dimensions 8
                                 :keep_alive -1}))})
      (.then #(vector (.-status %) (.json %)))
      (.then (fn [[status body]] (.then body #(vector status %))))))

(defn -main [& [bundle-path]]
  (let [manifest (bundle/load-bundle bundle-path)
        expected (into (:prompt-ids manifest)
                       (take 2 (:generated-ids manifest)))
        expected-format (get-in manifest [:details :format])
        context-length (get-in manifest [:config :context-length])
        embed-dim (get-in manifest [:config :embed-dim])]
    (-> (gpu/request-device)
        (.then
         (fn [request]
           (let [backend (gpu/backend request)
                 baseline (gpu/backend-stats backend)
                 model-size (.-size (js/Deno.statSync bundle-path))
                 events (atom [])
                 load-fn (fn [descriptor]
                           (swap! events conj [:load (:name descriptor)])
                           (resource/load-resource
                            backend descriptor
                            {:pool-blocks 64 :block-size 2 :max-running 2}))
                 unload-fn (fn [loaded]
                             (swap! events conj [:unload
                                                 (get-in loaded [:descriptor :name])])
                             (resource/unload-resource! loaded))
                 registry*
                 (reduce registry/register
                         (registry/registry (quot (* model-size 3) 2)
                                            load-fn unload-fn)
                         [(assoc (resource/descriptor "model-a:latest" bundle-path)
                                 :digest "sha256:a"
                                 :chat-template "{{ '<|im_start|>' }}")
                          (assoc (resource/descriptor "model-b:latest" bundle-path)
                                 :digest "sha256:b")])
                 runtime* (registry-runtime/runtime registry*)
                 router* (registry-ollama/router runtime*)
                 ids (atom 0)
                 service (assoc (registry-ollama/service
                                 router* {:version "0.12.0-registry-metal"})
                                :request-id-fn
                                #(keyword (str "registry-" (swap! ids inc))))
                 server (http/serve! service {:hostname "127.0.0.1" :port 0})
                 base (str "http://127.0.0.1:" (.-port (.-addr server)))
                 generate-url (str base "/api/generate")
                 tags-url (str base "/api/tags")
                 ps-url (str base "/api/ps")
                 show-url (str base "/api/show")
                 chat-url (str base "/api/chat")
                 embed-url (str base "/api/embed")
                 copy-url (str base "/api/copy")
                 delete-url (str base "/api/delete")
                 openai-models-url (str base "/v1/models")
                 openai-chat-url (str base "/v1/chat/completions")
                 openai-embed-url (str base "/v1/embeddings")]
             (println "Real portable Llama registry routing on"
                      (gpu/adapter-description request))
             (-> (mutate-model copy-url "POST"
                               {:source "model-a:latest"
                                :destination "model-a:backup"})
                 (.then
                  (fn [copy-result]
                    (-> (json-get tags-url)
                        (.then #(hash-map :copy-result copy-result
                                         :copied-tags %)))))
                 (.then
                  (fn [state]
                    (-> (mutate-model delete-url "DELETE"
                                      {:model "model-a:backup"})
                        (.then #(assoc state :delete-result %)))))
                 (.then
                  (fn [state]
                    (-> (json-get tags-url)
                        (.then #(assoc state :deleted-tags %)))))
                 (.then
                  (fn [lifecycle]
                    (-> (js/Promise.all
                         #js [(json-get ps-url) (show show-url "model-a:latest")
                              (show show-url "missing:latest")])
                        (.then #(hash-map :lifecycle lifecycle :initial %)))))
                 (.then
                  (fn [initial]
                    (-> (post generate-url "model-a:latest" -1)
                        (.then #(assoc initial :a %)))))
                 (.then
                  (fn [state]
                    (-> (js/Promise.all #js [(json-get tags-url) (json-get ps-url)
                                             (chat chat-url "model-a:latest")
                                             (embed embed-url "model-a:latest")
                                             (invalid-embed embed-url "model-a:latest")])
                        (.then #(assoc state :tags-a (aget % 0) :ps-a (aget % 1)
                                      :chat-a (aget % 2) :embed-a (aget % 3)
                                      :invalid-embed (aget % 4))))))
                 (.then
                  (fn [state]
                    (-> (openai-chat openai-chat-url "model-a:latest")
                        (.then #(assoc state :openai-chat %)))))
                 (.then
                  (fn [state]
                    (-> (openai-embed openai-embed-url "model-a:latest")
                        (.then #(assoc state :openai-embed %)))))
                 (.then
                  (fn [state]
                    (-> (json-get openai-models-url)
                        (.then #(assoc state :openai-models %)))))
                 (.then
                  (fn [state]
                    (-> (post generate-url "model-b:latest" 0)
                        (.then #(assoc state :b %)))))
                 (.then
                  (fn [state]
                    (-> (js/Promise.all #js [(json-get tags-url) (json-get ps-url)])
                        (.then #(assoc state :tags-b (aget % 0) :ps-b (aget % 1))))))
                 (.then
                  (fn [{:keys [lifecycle initial a b tags-a tags-b ps-a ps-b chat-a
                               embed-a invalid-embed openai-chat openai-embed
                               openai-models]}]
                    (let [context-a (vec (js->clj (.-context a)))
                          context-b (vec (js->clj (.-context b)))
                          rows-a (js->clj (.-models tags-a)
                                          :keywordize-keys true)
                          rows-b (js->clj (.-models tags-b)
                                          :keywordize-keys true)
                          loaded-a (into {} (map (juxt :name :loaded) rows-a))
                          loaded-b (into {} (map (juxt :name :loaded) rows-b))
                          stats-before-expire (registry-runtime/stats runtime*)
                          parity? (= expected context-a context-b)
                          tags? (and (= true (loaded-a "model-a:latest"))
                                     (= false (loaded-a "model-b:latest"))
                                     (= false (loaded-b "model-a:latest"))
                                     (= true (loaded-b "model-b:latest")))
                          eviction? (= 1 (:evictions stats-before-expire))
                          initial-ps (aget initial 0)
                            [show-status show-body] (js->clj (aget initial 1)
                                                               :keywordize-keys true)
                            [missing-status _] (js->clj (aget initial 2)
                                                        :keywordize-keys true)
                            ps-a-rows (js->clj (.-models ps-a) :keywordize-keys true)
                            ps-b-rows (js->clj (.-models ps-b) :keywordize-keys true)
                            management?
                            (and (zero? (.-length (.-models initial-ps)))
                                 (= 200 show-status) (= 404 missing-status)
                                 (= expected-format
                                    (get-in show-body [:details :format]))
                                 (= "llama" (get-in show-body [:details :family]))
                                 (= "{{ '<|im_start|>' }}" (:template show-body))
                                 (= #{"completion" "embedding"}
                                    (set (:capabilities show-body)))
                                 (= context-length
                                    (get-in show-body [:model_info
                                                       :llama.context_length]))
                                 (= ["model-a:latest"] (mapv :name ps-a-rows))
                                 (= ["model-b:latest"] (mapv :name ps-b-rows))
                                 (pos? (:size_vram (first ps-a-rows)))
                                 (= context-length
                                    (:context_length (first ps-a-rows))))
                            chat? (and (true? (.-done chat-a))
                                       (= "assistant" (.. chat-a -message -role))
                                       (string? (.. chat-a -message -content)))
                            embeddings (js->clj (.-embeddings embed-a))
                            [invalid-embed-status _] (js->clj invalid-embed)
                            embed? (and (= [embed-dim embed-dim]
                                           (mapv count embeddings))
                                        (= 400 invalid-embed-status)
                                        (every? #(< (js/Math.abs (- 1.0
                                                                   (js/Math.sqrt
                                                                    (reduce + (map (fn [x] (* x x)) %)))))
                                                    1.0e-5)
                                                embeddings))
                            [copy-status _] (:copy-result lifecycle)
                            [delete-status _] (:delete-result lifecycle)
                            copied-names (->> (.-models (:copied-tags lifecycle))
                                              (js->clj)
                                              (map #(get % "name")) set)
                            deleted-names (->> (.-models (:deleted-tags lifecycle))
                                               (js->clj)
                                               (map #(get % "name")) set)
                            lifecycle-api?
                            (and (= 200 copy-status) (= 200 delete-status)
                                 (contains? copied-names "model-a:backup")
                                 (not (contains? deleted-names "model-a:backup")))
                            openai?
                            (and (string?
                                  (some-> openai-chat .-choices (aget 0)
                                          .-message .-content))
                                 (= 2 (.-length (.-data openai-embed)))
                                 (= "list" (.-object openai-models))
                                 (= 2 (.-length (.-data openai-models))))]
                      (registry-runtime/expire! runtime* (+ 1000 (.now js/Date)))
                      (.shutdown server)
                      (let [stats (registry-runtime/stats runtime*)
                            released? (fixture/quiescent?
                                       baseline (gpu/backend-stats backend))
                            lifecycle? (= [[:load "model-a:latest"]
                                           [:load "model-b:latest"]
                                           [:unload "model-a:latest"]
                                           [:unload "model-b:latest"]]
                                          @events)]
                        (println "model-name routed CPU parity:"
                                 (if parity? "passed" "failed"))
                        (println "dynamic tags follow residency:"
                                 (if tags? "passed" "failed"))
                        (println "Ollama ps/show follow Metal residency:"
                                 (if management? "passed" "failed"))
                        (println "Ollama chat runs through resident Metal model:"
                                 (if chat? "passed" "failed"))
                        (println "Ollama normalized embeddings run on Metal:"
                                 (if embed? "passed" "failed"))
                        (println "Ollama copy/delete mutate live catalog:"
                                 (if lifecycle-api? "passed" "failed"))
                        (println "OpenAI compatibility uses resident Metal model:"
                                 (if openai? "passed" "failed"))
                        (println "inactive LRU eviction:"
                                 (if eviction? "passed" "failed"))
                        (println "load/unload exactly once:"
                                 (if lifecycle? "passed" "failed"))
                        (println "registry resident bytes:" (:resident-bytes stats))
                        (println "GPU baseline restored:"
                                 (if released? "passed" "failed"))
                        (when-not (and parity? tags? management? chat? embed?
                                       lifecycle-api? openai? eviction? lifecycle? released?
                                       (zero? (:resident-bytes stats)))
                          (throw (js/Error.
                                  "real portable registry verification failed")))))))))))
        (.then #(js/Deno.exit 0))
        (.catch (fn [error]
                  (println "ERROR:" (or (.-stack error) (str error)))
                  (js/Deno.exit 1))))))

(set! *main-cli-fn* -main)
