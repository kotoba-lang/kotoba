(ns torch.deno-public-gguf-continuous-http-verify
  "Concurrent Ollama HTTP requests sharing one real GGUF paged Metal engine."
  (:require [num.array :as arr]
            [num.deno-gpu :as gpu]
            [torch.continuous :as continuous]
            [torch.continuous-ollama :as continuous-http]
            [torch.deno-public-gguf-continuous-verify :as fixture]
            [torch.deno-public-gguf-metal-verify :as metal]
            [torch.kv-cache :as kv]
            [torch.metal-bundle :as bundle]
            [torch.num-backend :as nb]
            [torch.ollama-http :as http]
            [torch.paged-runtime :as paged]
            [torch.tokenizer :as tokenizer]))

(defn- ndjson [response]
  (-> (.text response)
      (.then (fn [body]
               (mapv #(js->clj (js/JSON.parse %) :keywordize-keys true)
                     (.split (.trim body) "\n"))))))

(defn- abort-after-first [post payload result]
  (let [aborter (js/AbortController.)]
    (-> (post payload (.-signal aborter))
        (.then (fn [response]
                 (let [reader (.getReader (.-body response))]
                   (-> (.read reader)
                       (.then (fn [_] (.cancel reader)))
                       (.then (fn [_]
                                (.abort aborter)
                                (js/Promise.
                                 (fn [resolve _]
                                   (js/setTimeout #(resolve result) 100))))))))))))

(defn -main [& [bundle-path]]
  (let [bundle (bundle/load-bundle bundle-path)]
    (-> (gpu/request-device)
        (.then
         (fn [request]
           (let [backend (gpu/backend request)
                 baseline (gpu/backend-stats backend)
                 {:keys [embed-dim head-count kv-head-count block-count vocab]}
                 (:config bundle)
                 head-dim (quot embed-dim head-count)
                 model* (metal/build-model (:config bundle))
                 weights (metal/upload-weights backend (:weights bundle))
                 storages (mapv (fn [_]
                                  (fixture/storage backend 16 2 head-count
                                                   kv-head-count head-dim))
                                (range block-count))
                 runtimes (mapv #(paged/runtime (kv/pool 16 2) %) storages)
                 batch-calls (atom [])
                 step-fn
                 (fn [token runtimes request-id]
                   (let [token* (arr/from-vec backend [token] [1])
                         step (nb/llama-lm-paged-step
                               model* weights token* runtimes request-id)
                         logits (:logits step)]
                     (arr/release! token*)
                     (-> (arr/->vec logits)
                         (.then (fn [values]
                                  (arr/release! logits)
                                  (assoc step :logits (vec values)))))))
                 batch-step-fn
                 (fn [tokens runtimes request-ids]
                   (swap! batch-calls conj request-ids)
                   (let [tokens* (arr/from-vec backend tokens [(count tokens) 1])
                         step (nb/llama-lm-paged-batch-step
                               model* weights tokens* runtimes request-ids)
                         logits (:logits step)]
                     (arr/release! tokens*)
                     (-> (arr/->vec logits)
                         (.then (fn [values]
                                  (arr/release! logits)
                                  (assoc step :logits
                                         (mapv vec (partition vocab values))))))))
                 engine (continuous/engine runtimes step-fn batch-step-fn 2
                                           {:max-waiting 4})
                 host* (continuous-http/host
                        engine (tokenizer/tokenizer (:tokenizer bundle)))
                 ids (atom 0) cancellations (atom [])
                 service {:version "0.12.0-continuous-metal"
                          :models [{:name "tiny-random-llama:latest"}]
                          :request-id-fn #(keyword (str "http-" (swap! ids inc)))
                          :generate-stream! #(js/Promise.resolve
                                              (continuous-http/submit-stream!
                                               host* %1 %2))
                          :generate! #(continuous-http/submit! host* %1 %2)
                          :cancel! (fn [id reason]
                                     (swap! cancellations conj [id reason])
                                     (continuous-http/cancel! host* id reason))}
                 server (http/serve! service {:hostname "127.0.0.1" :port 0})
                 url (str "http://127.0.0.1:" (.-port (.-addr server))
                          "/api/generate")
                 body (fn [prompt stream tokens]
                        (js/JSON.stringify
                         (clj->js {:model "tiny-random-llama:latest"
                                   :prompt prompt :stream stream
                                   :options {:temperature 0.0
                                             :num_predict tokens}})))
                 post (fn [payload signal]
                        (js/fetch url
                                  (clj->js (cond-> {:method "POST"
                                                   :headers {"content-type"
                                                             "application/json"}
                                                   :body payload}
                                            signal (assoc :signal signal)))))
                 expected (into {} (map (juxt :prompt :generated-ids)
                                        (:continuous-fixtures bundle)))]
             (println "Concurrent real Ollama continuous HTTP on"
                      (gpu/adapter-description request))
             (-> (js/Promise.all
                  #js [(-> (post (body "Hello" true 2) nil) (.then ndjson))
                       (-> (post (body "Hi there" false 2) nil) (.then #(.json %)))])
                 (.then
                  (fn [responses]
                    (let [stream (aget responses 0)
                          nonstream (aget responses 1)
                          stream-context (:context (last stream))
                          nonstream-context (vec (js->clj (.-context nonstream)))
                          a (first (:continuous-fixtures bundle))
                          b (second (:continuous-fixtures bundle))
                          expected-a (into (:prompt-ids a) (expected "Hello"))
                          expected-b (into (:prompt-ids b) (expected "Hi there"))]
                      {:parity? (and (= expected-a stream-context)
                                     (= expected-b nonstream-context))
                       :stream-context stream-context
                       :nonstream-context nonstream-context})))
                 (.then
                  #(abort-after-first post (body "Hello world" true 12) %))
                 (.then
                  (fn [result]
                    (-> @(:tail host*)
                        (.catch (fn [_] nil))
                        (.then (fn [_] result)))))
                 (.then
                  (fn [{:keys [parity?]}]
                    (let [engine* @(:engine host*)
                          fused? (some #(> (count %) 1) @batch-calls)
                          cancelled? (some #(= :cancelled (:reason %))
                                           (vals (:completed engine*)))
                          pools-free? (every?
                                       #(and (= 16 (count (get-in % [:pool :free])))
                                             (kv/valid? (:pool %)))
                                       (:runtimes engine*))]
                      (println "engine running:" (keys (:running engine*))
                               "completed reasons:"
                               (into {} (map (fn [[id value]] [id (:reason value)]))
                                     (:completed engine*))
                               "service cancellations:" @cancellations)
                      (println "concurrent stream/non-stream CPU parity:"
                               (if parity? "passed" "failed"))
                      (println "HTTP requests shared fused microbatch:"
                               (if fused? "passed" "failed"))
                      (println "disconnect cancellation:"
                               (if cancelled? "passed" "failed"))
                      (println "paged blocks reusable:"
                               (if pools-free? "passed" "failed"))
                      (.shutdown server)
                      (continuous-http/close! host*)
                      (doseq [{:keys [key-pool value-pool]} storages]
                        (arr/release-all! [key-pool value-pool]))
                      (nb/release-weights! weights)
                      (let [released? (fixture/quiescent?
                                       baseline (gpu/backend-stats backend))]
                        (println "GPU baseline restored:"
                                 (if released? "passed" "failed"))
                        (when-not (and parity? fused? cancelled?
                                       pools-free? released?)
                          (throw (js/Error.
                                  "continuous Ollama HTTP verification failed")))))))))))
        (.then #(js/Deno.exit 0))
        (.catch (fn [error]
                  (println "ERROR:" (or (.-stack error) (str error)))
                  (js/Deno.exit 1))))))

(set! *main-cli-fn* -main)
