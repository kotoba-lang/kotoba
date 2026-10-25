(ns kotodama.verify.qwen4exp-flash-next-b70-resident
  "Verify the checked-in B70 resident observation without promoting capacity to
  synchronous long-context qualification."
  (:require [json.data-json :as json]))

(defn -main [& _]
  (let [evidence (json/read-str
                  (slurp "verify/evidence/qwen4exp-flash-next-b70-resident-20260828.json"))
        config (get evidence "resident_configuration")
        generation (get evidence "clean_generation")
        restart (get evidence "restart_proof")
        qualification (get evidence "qualification")]
    (when-not (and (= 32768 (get config "context_tokens"))
                   (= 1 (get config "parallel_slots"))
                   (= 18 (get config "gpu_layers"))
                   (false? (get config "mtp_enabled"))
                   (= (get generation "expected_content")
                      (get generation "observed_content"))
                   (= "stop" (get generation "finish_reason"))
                   (pos? (get generation "prompt_tok_s"))
                   (pos? (get generation "generation_tok_s"))
                   (= 200 (get restart "health_http_status"))
                   (= 32768 (get restart "reported_context_tokens"))
                   (= 201 (get restart "join_enrollment_http_status"))
                   (true? (get qualification "resident_short_generation_qualified"))
                   (true? (get qualification "restart_recovery_qualified"))
                   (true? (get qualification "fleet_join_qualified"))
                   (false? (get qualification "mtp_qualified"))
                   (false? (get qualification "synchronous_long_context_qualified")))
      (throw (ex-info "B70 resident evidence crossed a qualification boundary"
                      qualification)))
    (prn qualification)))
