(ns torch.deno-device-sampling-verify
  "End-to-end native WebGPU bounded and full-softmax sampling verification."
  (:require [num.deno-gpu :as gpu]
            [torch.continuous :as continuous]
            [torch.continuous-ollama :as continuous-ollama]
            [torch.metal-resource :as resource]
            [torch.ollama :as ollama]))

(defn -main [& [bundle-path]]
  (when-not bundle-path
    (throw (ex-info "bundle path is required" {})))
  (-> (gpu/request-device)
      (.then
       (fn [request]
         (let [backend (gpu/backend request)
               baseline (gpu/backend-stats backend)
               loaded (resource/load-resource
                       backend (resource/descriptor "tiny:latest" bundle-path)
                       {:pool-blocks 16 :block-size 4 :max-running 2
                        :max-waiting 4 :device-sampling? true})
               host* (:host loaded)
               resource-baseline (gpu/backend-stats backend)
               cancel-quiescent? (atom false)
               normalized
               (ollama/normalize-generate-request
                {:model "tiny:latest" :prompt "Hello" :stream false
                 :options {:temperature 0.7 :top_k 8 :top_p 0.9
                           :repeat_penalty 1.2
                           :num_predict 4}})
               normalized-full
               (ollama/normalize-generate-request
                {:model "tiny:latest" :prompt "Hello" :stream false
                 :options {:temperature 0.7 :top_p 1.0
                           :repeat_penalty 1.2
                           :num_predict 4}})
               normalized-nucleus
               (ollama/normalize-generate-request
                {:model "tiny:latest" :prompt "Hello" :stream false
                 :options {:temperature 0.7 :top_p 0.9
                           :repeat_penalty 1.2
                           :num_predict 4}})]
           (-> (continuous/admit-async
                (:engine
                 (continuous/submit @(:engine host*) :cancel-before-sample [1]
                                    {:temperature 0.0 :repetition-penalty 1.0
                                     :max-new-tokens 4 :eos-id -1})))
               (.then
                (fn [admitted]
                  (let [cancelled (:engine
                                   (continuous/cancel admitted
                                                      :cancel-before-sample))
                        after-cancel (gpu/backend-stats backend)]
                    (reset! (:engine host*) cancelled)
                    (reset! cancel-quiescent?
                            (and (= (:live-buffers resource-baseline)
                                    (:live-buffers after-cancel))
                                 (= (:live-bytes resource-baseline)
                                    (:live-bytes after-cancel))))
                    (continuous-ollama/submit! host* normalized
                                               {:request-id :device-top-k}))))
               (.then
                (fn [_]
                  (continuous-ollama/submit! host* normalized-full
                                             {:request-id :device-full-softmax})))
               (.then
                (fn [_]
                  (continuous-ollama/submit! host* normalized-nucleus
                                             {:request-id :device-nucleus})))
               (.then
                (fn [_]
                  (let [generated (get-in @(:engine host*)
                                          [:completed :device-top-k
                                           :generated-ids])
                        generated-full
                        (get-in @(:engine host*)
                                [:completed :device-full-softmax :generated-ids])
                        generated-nucleus
                        (get-in @(:engine host*)
                                [:completed :device-nucleus :generated-ids])
                        sampling @(:sampling-stats loaded)
                        selected (gpu/backend-stats backend)
                        selection-bytes
                        (- (:selection-readback-bytes selected 0)
                           (:selection-readback-bytes baseline 0))
                        selection-calls
                        (- (:selection-readbacks selected 0)
                           (:selection-readbacks baseline 0))]
                    (resource/unload-resource! loaded)
                    (let [after (gpu/backend-stats backend)
                          result
                          {:adapter (gpu/adapter-description request)
                           :generated-ids generated
                           :expected-ids [23639 27919 26381 7335]
                           :full-softmax-generated-ids generated-full
                           :full-softmax-expected-ids [15988 16001 16005 16009]
                           :nucleus-generated-ids generated-nucleus
                           :nucleus-expected-ids [7119 2862 22514 30876]
                           :sampling sampling
                           :selection-readbacks selection-calls
                           :selection-readback-bytes selection-bytes
                           :full-logits-readback-bytes 0
                           :cancel-before-sample-quiescent? @cancel-quiescent?
                           :buffers-quiescent?
                           (and (= (:live-buffers baseline)
                                   (:live-buffers after))
                                (= (:live-bytes baseline)
                                   (:live-bytes after)))}]
                      (println (js/JSON.stringify (clj->js result)))
                      (when-not (and (= (:generated-ids result)
                                        (:expected-ids result))
                                     (= (:full-softmax-generated-ids result)
                                        (:full-softmax-expected-ids result))
                                     (= (:nucleus-generated-ids result)
                                        (:nucleus-expected-ids result))
                                     (= {:device-greedy-tokens 0
                                         :device-sampled-tokens 12
                                         :host-sampled-tokens 0}
                                        sampling)
                                     (= 12 selection-calls)
                                     (= 48 selection-bytes)
                                     (:cancel-before-sample-quiescent? result)
                                     (:buffers-quiescent? result))
                        (throw (ex-info "device sampling verification failed"
                                        result)))))))))))
      (.then (fn [_] (js/Deno.exit 0)))
      (.catch (fn [error]
                (js/console.error (or (.-stack error) error))
                (js/Deno.exit 1)))))

(set! *main-cli-fn* -main)
