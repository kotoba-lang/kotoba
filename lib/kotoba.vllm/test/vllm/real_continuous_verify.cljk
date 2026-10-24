(ns vllm.real-continuous-verify
  "Two concurrent Ollama HTTP requests sharing one continuous Metal batch."
  (:require [json.data-json :as json]
            [vllm.metal-worker :as metal]
            [vllm.ollama :as ollama]
            [vllm.ollama-server :as server]
            [vllm.scheduler :as scheduler])
  (:import [java.net URI]
           [java.net.http HttpClient HttpRequest HttpRequest$BodyPublishers
            HttpResponse$BodyHandlers]))

(defn- request [port payload]
  (-> (HttpRequest/newBuilder
       (URI/create (str "http://127.0.0.1:" port "/api/generate")))
      (.header "Content-Type" "application/json")
      (.POST (HttpRequest$BodyPublishers/ofString (json/write-str payload)))
      .build))

(defn -main [& [path worker-path]]
  (when-not path (throw (ex-info "usage: real-continuous-verify model.gguf [worker]" {})))
  (with-open [worker (metal/start ["deno" "run" "--allow-all"
                                  (or worker-path "../num/target/deno-q8-worker.cjs")])
              runtime (ollama/runtime {:accelerator worker :workers 2
                                       :batch-window-ms 30 :max-batch-size 8})]
    (ollama/load! runtime "continuous" path)
    (with-open [http (server/start! runtime {:port 0 :threads 2})]
      (let [clients [(HttpClient/newHttpClient) (HttpClient/newHttpClient)]
            payload {"model" "continuous" "prompt" "Once upon a time"
                     "num_predict" 1 "stream" false
                     "options" {"temperature" 0}}
            started (System/nanoTime)
            futures (mapv #(.sendAsync % (request (:port http) payload)
                                       (HttpResponse$BodyHandlers/ofString)) clients)
            responses (mapv #(.get %) futures)
            bodies (mapv #(json/read-str (.body %)) responses)
            stats (metal/stats worker)
            scheduler-stats (scheduler/stats (:scheduler runtime))
            prompt-tokens (get (first bodies) "prompt_eval_count")
            report {:statuses (mapv #(.statusCode %) responses)
                    :texts (mapv #(get % "response") bodies)
                    :prompt-tokens prompt-tokens :sequences 2
                    :metal-submissions (:submissions stats)
                    :remaining-kv-handles (:kv-handles stats)
                    :cohorts (:recent-batch-sizes scheduler-stats)
                    :expected-shared-submissions (* 24 prompt-tokens)
                    :seconds (/ (- (System/nanoTime) started) 1.0e9)}]
        (println (pr-str report))
        (when-not (and (= [200 200] (:statuses report))
                       (= 1 (count (distinct (:texts report))))
                       (= (:expected-shared-submissions report)
                          (:metal-submissions report))
                       (zero? (:remaining-kv-handles report)))
          (throw (ex-info "continuous HTTP batch verification failed" report)))))))
