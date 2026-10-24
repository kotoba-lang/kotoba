(ns vllm.real-batch-verify
  "Verify sequence-wide Metal projection batching on a real GGUF."
  (:require [vllm.gguf :as gguf]
            [vllm.llama :as llama]
            [vllm.metal-worker :as metal]))

(defn- max-error [^floats left ^floats right]
  (loop [i 0 result 0.0]
    (if (= i (alength left)) result
      (recur (inc i) (max result (Math/abs (- (aget left i) (aget right i))))))))

(defn -main [& [path worker-path]]
  (when-not path (throw (ex-info "usage: real-batch-verify model.gguf [worker]" {})))
  (with-open [cpu-file (gguf/open-file path) gpu-file (gguf/open-file path)
              worker (metal/start ["deno" "run" "--allow-all"
                                   (or worker-path "../num/target/deno-q8-worker.cjs")])]
    (let [cpu (llama/load-gguf cpu-file)
          gpu (llama/load-gguf gpu-file {:accelerator worker})
          tokens [1 2]
          expected (mapv (fn [token]
                           (:logits (llama/step! cpu (llama/new-state cpu) token))) tokens)
          states (mapv (fn [_] (llama/new-state gpu)) tokens)
          started (System/nanoTime)
          actual (mapv :logits (llama/step-batch! gpu states tokens))
          positions (mapv #(deref (:position %)) states)
          _ (doseq [state states] (llama/close-state! state))
          stats (metal/stats worker)
          errors (mapv max-error expected actual)
          report {:sequences 2 :max-absolute-errors errors
                  :metal-submissions (:submissions stats)
                  :single-gemv (:gemv stats) :batched-gemv (:gemv-many stats)
                  :single-attention (:attention stats)
                  :batched-attention (:attention-many stats)
                  :resident-handles (:handles stats)
                  :resident-kv-handles (:kv-handles stats)
                  :seconds (/ (- (System/nanoTime) started) 1.0e9)}]
      (println (pr-str report))
      (when-not (and (every? #(< % 0.02) errors)
                     (= 24 (:submissions stats))
                     (= 6 (:attention-many stats))
                     (zero? (or (:attention stats) 0))
                     (= [1 1] positions)
                     (zero? (:kv-handles stats)))
        (throw (ex-info "real sequence batch diverged" report)))
      (llama/close-model! gpu))))
