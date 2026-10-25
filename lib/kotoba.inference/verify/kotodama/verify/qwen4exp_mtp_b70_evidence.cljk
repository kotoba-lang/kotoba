(ns kotodama.verify.qwen4exp-mtp-b70-evidence
  "Verify the checked-in B70 observation as a disqualification record."
  (:require [json.data-json :as json]
            [kotodama.inference.qwen4exp :as qwen4exp]))

(defn -main [& _]
  (let [evidence (json/read-str
                  (slurp "verify/evidence/qwen4exp-mtp-b70-20260828.json"))
        parity (get evidence "parity")
        performance (get evidence "end_to_end_output_tok_s")
        report {"off_deterministic" (get parity "mtp_off_deterministic")
                "on_deterministic" (get parity "mtp_on_deterministic")
                "token_parity" (get parity "exact_token_parity")
                "end_to_end_speedup" (get performance "on_over_off")}
        qualification (qwen4exp/execution-qualification report)]
    (when-not (and (= :unstable-mtp (:kotodama/disqualification qualification))
                   (false? (:kotodama/mtp-execution-qualified? qualification))
                   (false? (:kotodama/mtp-optimization-qualified? qualification))
                   (true? (get-in evidence ["postcondition" "health_endpoint_ok"])))
      (throw (ex-info "B70 evidence no longer matches its fail-closed qualification"
                      qualification)))
    (prn qualification)))
