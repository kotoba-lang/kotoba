(ns kotodama.verify.gemma4-kvcache-smoke
  "Verify the KV-cache is a pure optimization: greedy generation with the cache
  ON must produce token-for-token IDENTICAL output to a from-scratch run with
  the cache OFF, and be faster. Reports real tokens/sec for both."
  (:require [kotodama.inference.host.jvm :as host]
            [kotodama.inference.decode :as decode]))

(defn- run [session prompt max-tokens]
  (host/reset-cache! session)
  (let [tok (:kotodama/tokenizer session)
        t0 (System/nanoTime)
        result (decode/generate {:kotodama/tokenizer tok
                                 :kotodama/forward-fn (fn [ids] (host/forward-logits session ids))
                                 :kotodama/prompt prompt
                                 :kotodama/max-tokens max-tokens
                                 :kotodama/eos-token-ids (:kotodama/eos-token-ids session)})
        secs (/ (- (System/nanoTime) t0) 1.0e9)]
    {:ids (:kotodama/generated-token-ids result)
     :text (:kotodama/text result)
     :secs secs
     :tok/s (/ (count (:kotodama/generated-token-ids result)) secs)}))

(defn -main [& _]
  (let [prompt (or (System/getenv "KOTODAMA_VERIFY_PROMPT") "The capital of France is")
        max-tokens (Long/parseLong (or (System/getenv "KOTODAMA_VERIFY_MAX_TOKENS") "6"))
        cache-weights? (not= "0" (or (System/getenv "CACHE_WEIGHTS") "1"))
        base (host/load-model {:kotodama/model "gemma4:e4b" :kotodama/cache-weights? cache-weights?})]
    (println "prompt:" (pr-str prompt) " max-tokens:" max-tokens " weight-cache:" cache-weights?)
    ;; warm the weight cache so timing reflects steady state, not first-touch IO
    (when cache-weights?
      (host/forward-logits base [(:kotodama.tokenizer/bos-token-id (:kotodama/tokenizer base))])
      (host/reset-cache! base))
    (let [off (run (assoc base :use-kv-cache? false) prompt max-tokens)
          on  (run (assoc base :use-kv-cache? true) prompt max-tokens)]
      (println "kv-cache OFF ids:" (:ids off))
      (println "kv-cache ON  ids:" (:ids on))
      (println "identical? " (= (:ids off) (:ids on)))
      (println (format "OFF: %.1fs  %.4f tok/s" (:secs off) (:tok/s off)))
      (println (format "ON : %.1fs  %.4f tok/s  (%.2fx)" (:secs on) (:tok/s on)
                       (/ (:tok/s on) (:tok/s off))))
      (println "text (ON):" (pr-str (:text on)))
      (host/close-model base)
      (when-not (= (:ids off) (:ids on))
        (throw (ex-info "KV-cache changed the output!" {:off (:ids off) :on (:ids on)}))))))
