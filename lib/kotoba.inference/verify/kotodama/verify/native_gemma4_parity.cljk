(ns kotodama.verify.native-gemma4-parity
  "Fixed raw-completion gate: the native kotodama host against a RECORDED
  oracle.

  ⚠ IT USED TO BE 'versus live Ollama', and that is what changed on 2026-09-09.
  The old shape ran `POST 127.0.0.1:11434/api/generate` and asserted three
  things: that Ollama still answered the recorded text, that this host agreed
  with Ollama, and that this host's token id was the recorded one. The middle
  assertion is the dependence -- it made a third-party server the reference for
  what this stack should say -- and the owner's direction is that no vLLM,
  Ollama, MLX or llama.cpp sits underneath.

  Removing it costs one thing and it should be said plainly: nothing here now
  notices if the RECORDED constants are themselves wrong. They were not made up
  -- ` Paris` and token 9079 were measured against live Ollama 0.31.1 greedy
  when this gate was written, and that measurement is what the constants are --
  but from here on they are an oracle rather than a comparison. That is the
  correct trade: a value checked against a service that can change underneath
  you is not a fixed oracle, it is a moving one that looks fixed.

  What is NOT lost: this still fails if the native host's answer moves, which
  is the whole reason the gate exists."
  (:require [kotodama.inference.host.jvm :as host]))

(def model "gemma4:e4b")
(def prompt "The capital of France is")

;; Measured against live Ollama 0.31.1 greedy when this gate was written, and
;; recorded here so the comparison no longer needs it running.
(def expected-text " Paris")
(def expected-token-id 9079)

(defn -main [& _]
  (let [t0 (System/nanoTime)
        local (host/generate {:kotodama/model model
                              :kotodama/prompt prompt
                              :kotodama/max-tokens 1
                              :kotodama/cache-weights? false
                              :kotodama/dbg {:native-k-dot? true}})
        local-seconds (/ (- (System/nanoTime) t0) 1.0e9)
        local-text (:kotodama/text local)
        local-ids (:kotodama/generated-token-ids local)]
    ;; Both, not one. The text and the id can disagree -- a tokenizer change
    ;; moves one without the other -- and a gate that checked only the id would
    ;; call that a pass.
    (when-not (= expected-text local-text)
      (throw (ex-info "native Gemma4 text differs from the recorded oracle"
                      {:expected expected-text :actual local-text :ids local-ids})))
    (when-not (= [expected-token-id] local-ids)
      (throw (ex-info "native Gemma4 token id differs from the recorded oracle"
                      {:expected [expected-token-id] :actual local-ids})))
    (prn {:kotodama/native-gemma4-parity :ok
          :model model
          :prompt prompt
          :token-id expected-token-id
          :text local-text
          :oracle :recorded
          :seconds local-seconds})))
