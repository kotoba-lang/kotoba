(ns kotodama.verify.gemma4-e4b-ple-generate-smoke
  "Real Gemma4 GGUF -> end-to-end generation through the promoted, PLE-aware
  library host adapter `kotodama.inference.host.jvm` (KV-cache on by default).

  This is the successor to `gemma4-e4b-generate-smoke` (which runs the older
  `stable-block-forward`, a plain transformer block without per-layer
  embeddings). It exercises the stable production entry point that
  murakumo-studio calls: `kotodama.inference.host.jvm/generate`.

  Env: KOTODAMA_VERIFY_PROMPT, KOTODAMA_VERIFY_MAX_TOKENS,
       KOTODAMA_TRACE_EDN (optional activation-fingerprint output path),
       KOTODAMA_FLOAT32=1 (ggml-like float32 projection accumulation probe),
       KOTODAMA_GGML_K_DOT=1 (Q8_K activation + Q4_K/Q6_K direct block-dot),
       KOTODAMA_NATIVE_K_DOT=1 (mmap + native C K-dot through JDK FFM),
       KOTODAMA_METAL_K_DOT=1 (persistent Deno WebGPU→Metal K-dot worker),
       CACHE_WEIGHTS=1 (keep dequantized weights in RAM, ~20GB, much faster)."
  (:require [kotodama.inference.host.jvm :as host]))

(defn -main [& _]
  (let [prompt (or (System/getenv "KOTODAMA_VERIFY_PROMPT") "The capital of France is")
        max-tokens (Long/parseLong (or (System/getenv "KOTODAMA_VERIFY_MAX_TOKENS") "16"))
        cache-weights? (= "1" (System/getenv "CACHE_WEIGHTS"))
        trace-path (System/getenv "KOTODAMA_TRACE_EDN")
        float32? (= "1" (System/getenv "KOTODAMA_FLOAT32"))
        ggml-k-dot? (= "1" (System/getenv "KOTODAMA_GGML_K_DOT"))
        native-k-dot? (= "1" (System/getenv "KOTODAMA_NATIVE_K_DOT"))
        metal-k-dot? (= "1" (System/getenv "KOTODAMA_METAL_K_DOT"))
        trace-events (atom [])
        t0 (System/nanoTime)
        result (host/generate {:kotodama/model "gemma4:e4b"
                               :kotodama/prompt prompt
                               :kotodama/max-tokens max-tokens
                               :kotodama/cache-weights? cache-weights?
                               :kotodama/dbg (cond-> {:float32-matmul? float32?
                                                     :ggml-k-dot? ggml-k-dot?
                                                     :native-k-dot? native-k-dot?
                                                     :metal-k-dot? metal-k-dot?}
                                               trace-path
                                               (assoc :trace-fn #(swap! trace-events conj %)))
                               :kotodama/on-token
                               (fn [id text nanos]
                                 (println (format "  [+%.1fs] %d %s" (/ nanos 1.0e9) id (pr-str text)))
                                 (flush))})
        secs (/ (- (System/nanoTime) t0) 1.0e9)]
    (when trace-path
      (spit trace-path (str (pr-str @trace-events) "\n"))
      (println "trace:     " trace-path "(" (count @trace-events) "events)"))
    (println "prompt:    " (pr-str prompt))
    (println "generated: " (pr-str (:kotodama/text result)))
    (println "stop:      " (:kotodama/stop-reason result))
    (println "tokens/sec:" (/ (count (:kotodama/generated-token-ids result)) secs))
    (prn {:kotodama/gemma4-e4b-ple-generate-smoke :ok
          :kotodama/prompt prompt
          :kotodama/generated-text (:kotodama/text result)
          :gemma4/block-count (:gemma4/block-count result)})))
