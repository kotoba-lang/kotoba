(ns torch.deno-public-gguf-metal-verify
  "Run an exported real GGUF checkpoint through the complete Llama graph on Metal."
  (:require [num.array :as arr]
            [num.deno-gpu :as gpu]
            [torch.generate :as generate]
            [torch.metal-bundle :as bundle]
            [torch.num-backend :as nb]))

(def build-model bundle/build-model)

(def upload-weights bundle/upload-weights)

(defn step-read [backend model* weights token-id caches]
  (let [token (arr/from-vec backend [token-id] [1])
        step (nb/llama-lm-step model* weights token caches)]
    (-> (arr/->vec (:logits step))
        (.then (fn [logits]
                 (arr/release! token)
                 (arr/release! (:logits step))
                 {:logits logits :caches (:caches step)})))))

(defn prefill [backend model* weights caches prompt-ids]
  (reduce (fn [pending token-id]
            (.then pending
                   (fn [{:keys [caches]}]
                     (step-read backend model* weights token-id caches))))
          (js/Promise.resolve {:caches caches}) prompt-ids))

(defn- generate-greedy [backend model* weights state token-count]
  (letfn [(advance [{:keys [logits caches generated]}]
            (if (= token-count (count generated))
              (js/Promise.resolve {:generated generated :caches caches})
              (let [token-id (generate/sample-token logits {:temperature 0.0})]
                (-> (step-read backend model* weights token-id caches)
                    (.then #(advance (assoc % :generated
                                            (conj generated token-id))))))))]
    (advance (assoc state :generated []))))

(defn -main [& [bundle-path]]
  (when-not bundle-path
    (throw (js/Error. "usage: deno ... bundle.edn")))
  (let [bundle-start (.now js/performance)
        bundle (bundle/load-bundle bundle-path)
        bundle-load-ms (- (.now js/performance) bundle-start)]
    (-> (gpu/request-device)
        (.then
         (fn [request]
           (let [backend (gpu/backend request)
                 baseline (gpu/backend-stats backend)
                 model* (build-model (:config bundle))
                 weights (upload-weights backend (:weights bundle))
                 caches (nb/init-llama-caches backend model* 32)
                 started (.now js/performance)]
             (println "Public GGUF full Llama on" (gpu/adapter-description request))
             (println "compact bundle read/decode ms:" (.toFixed bundle-load-ms 3))
             (-> (prefill backend model* weights caches (:prompt-ids bundle))
                 (.then #(generate-greedy backend model* weights % 4))
                 (.then
                  (fn [{:keys [generated caches]}]
                    (let [before-release (gpu/backend-stats backend)
                          _ (nb/release-llama-caches! caches)
                          _ (nb/release-weights! weights)
                          after-release (gpu/backend-stats backend)
                          elapsed (- (.now js/performance) started)
                          parity? (= generated (:generated-ids bundle))
                          released-buffers (- (:live-buffers before-release)
                                              (:live-buffers after-release))
                          released-bytes (- (:live-bytes before-release)
                                            (:live-bytes after-release))
                          release? (and (pos? released-buffers)
                                        (pos? released-bytes)
                                        (= (:live-buffers baseline)
                                           (:live-buffers after-release))
                                        (= (:live-bytes baseline)
                                           (:live-bytes after-release))
                                        (= (- (:created-buffers after-release)
                                              (:created-buffers baseline))
                                           (- (:destroyed-buffers after-release)
                                              (:destroyed-buffers baseline))))]
                      (println "prompt ids:" (:prompt-ids bundle))
                      (println "CPU expected:" (:generated-ids bundle))
                      (println "Metal generated:" generated)
                      (println "CPU/Metal greedy parity:"
                               (if parity? "passed" "failed"))
                      (println "Metal elapsed ms:" (.toFixed elapsed 3))
                      (println "weights+cache released:" released-buffers
                               "buffers /" released-bytes "bytes")
                      (println "remaining transient buffers:"
                               (- (:live-buffers after-release)
                                  (:live-buffers baseline)))
                      (when-not (and parity? release?)
                        (throw (js/Error. "public GGUF Metal verification failed"))))))))))
        (.then #(js/Deno.exit 0))
        (.catch (fn [error]
                  (println "ERROR:" (or (.-stack error) (str error)))
                  (js/Deno.exit 1))))))

(set! *main-cli-fn* -main)
