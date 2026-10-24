(ns vllm.real-prefix-verify
  "Verify device-to-device cloned KV prefix reuse on a real GGUF."
  (:require [vllm.metal-worker :as metal]
            [vllm.ollama :as ollama]))

(defn -main [& [path worker-path]]
  (when-not path (throw (ex-info "usage: real-prefix-verify model.gguf [worker]" {})))
  (with-open [worker (metal/start ["deno" "run" "--allow-all"
                                  (or worker-path "../num/target/deno-q8-worker.cjs")])
              runtime (ollama/runtime {:accelerator worker :workers 1
                                       :prefix-cache-capacity 2})]
    (ollama/load! runtime "prefix" path)
    (let [request {:method :post :path "/api/generate"
                   :body {"model" "prefix" "prompt" "Once upon a time"
                          "num_predict" 1 "stream" false
                          "options" {"temperature" 0}}}
          first-response (ollama/handle runtime request)
          after-first (metal/stats worker)
          second-response (ollama/handle runtime request)
          after-second (metal/stats worker)
          first-submissions (:submissions after-first)
          second-submissions (- (:submissions after-second) first-submissions)
          config (get-in @(:models runtime) ["prefix" :model :config])
          full-kv-bytes (* 2 4 (:block-count config) (:context-length config)
                           (:head-count-kv config) (:head-dim config))
          cache-stats (get-in (ollama/handle runtime {:method :get :path "/api/ps"})
                              [:body "models" 0 "prefix_cache"])
          report {:responses [(get-in first-response [:body "response"])
                              (get-in second-response [:body "response"])]
                  :first-projection-submissions first-submissions
                  :cached-projection-submissions second-submissions
                  :prefix-cache cache-stats :resident-kv (:kv-handles after-second)
                  :allocated-kv-bytes (:kv-bytes after-second)
                  :full-context-kv-bytes full-kv-bytes}]
      (println (pr-str report))
      (when-not (and (= 120 first-submissions) (= 24 second-submissions)
                     (= 1 (:entries cache-stats)) (= 1 (:kv-handles after-second))
                     (< (:kv-bytes after-second) full-kv-bytes)
                     (apply = (:responses report)))
        (throw (ex-info "real prefix cache verification failed" report))))))
